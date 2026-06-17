(function (exports, Laya) {
    'use strict';

    function ImageDataPolyfill() {
        let width, height, data;
        if (arguments.length == 3) {
            if (arguments[0] instanceof Uint8ClampedArray) {
                if (arguments[0].length % 4 !== 0) {
                    throw new Error("Failed to construct 'ImageData': The input data length is not a multiple of 4.");
                }
                if (arguments[0].length !== arguments[1] * arguments[2] * 4) {
                    throw new Error("Failed to construct 'ImageData': The input data length is not equal to (4 * width * height).");
                }
                else {
                    data = arguments[0];
                    width = arguments[1];
                    height = arguments[2];
                }
            }
            else {
                throw new Error("Failed to construct 'ImageData': parameter 1 is not of type 'Uint8ClampedArray'.");
            }
        }
        else if (arguments.length == 2) {
            width = arguments[0];
            height = arguments[1];
            data = new Uint8ClampedArray(arguments[0] * arguments[1] * 4);
        }
        else if (arguments.length < 2) {
            throw new Error("Failed to construct 'ImageData': 2 arguments required, but only " + arguments.length + " present.");
        }
        let imgdata = Laya.Browser.canvas.context.getImageData(0, 0, width, height);
        let arr = imgdata.data;
        for (let i = 0, n = data.length; i < n; i++)
            arr[i] = data[i];
        return imgdata;
    }
    if (!window.ImageData) {
        window.ImageData = ImageDataPolyfill;
    }

    const GROUP_COUNT = 5;
    class MgCacheManager {
        constructor(cacheRoot) {
            this.totalFileSize = 0;
            this.running = false;
            this.lastGroup = -1;
            this.lastGroupUsed = 0;
            this.toClear = 0;
            this.cacheRoot = cacheRoot;
            this.fileCache = new Map();
            this.cacheGroups = new Array(GROUP_COUNT);
            this.cacheGroups.fill(0);
            this.cacheRequest = [];
            this.toSaveManifestFlags = new Array(GROUP_COUNT);
        }
        start() {
            this.checkAndDeleteOldCacheDir();
            return this.createCacheDirs().then(() => this.loadAllManifests()).then(() => {
                Laya.ILaya.systemTimer.loop(MgCacheManager.processInterval, this, this.process);
            });
        }
        getFile(url) {
            let info = this.fileCache.get(url);
            if (!info)
                return Promise.resolve(null);
            info.accessTime = this.toSaveManifestRequest = performance.now();
            this.toSaveManifestFlags[info.group] = true;
            let cacheFilePath = `${this.cacheRoot}/${info.group}/${info.fileName}`;
            return Laya.PAL.fs.exists(cacheFilePath).then(exists => exists ? cacheFilePath : null);
        }
        addFile(url, tempFilePath) {
            Laya.PAL.fs.getFileSize(tempFilePath).then(size => this.cacheRequest.push({ url, tempFilePath, size }))
                .catch(err => {
                console.warn("[Cache]get file size error", Laya.getErrorMsg(err));
            });
        }
        clearAllCache() {
            this.toClear = 2;
        }
        process() {
            if (this.running)
                return;
            if (this.toClear != 0) {
                this.running = true;
                let clearFlag = this.toClear;
                this.toClear = 0;
                if ((clearFlag & 2) !== 0)
                    this.doClearAllCache().then(() => this.running = false);
                else
                    this.clearSpace(0).then(() => this.saveDirtyManifests()).then(() => this.running = false);
                return;
            }
            if (this.cacheRequest.length === 0) {
                if (this.toSaveManifestRequest != null && performance.now() - this.toSaveManifestRequest > MgCacheManager.saveAccessTimeInterval) {
                    this.toSaveManifestRequest = null;
                    this.running = true;
                    this.saveDirtyManifests().then(() => this.running = false);
                }
                return;
            }
            this.running = true;
            let files = this.cacheRequest.concat();
            this.cacheRequest.length = 0;
            let group = this.selectGroup(files.length);
            let needSpace = 0;
            for (let info of files)
                needSpace += info.size;
            let toClearSpace = this.totalFileSize + needSpace - MgCacheManager.spaceLimit;
            this.clearSpace(toClearSpace)
                .then(() => this.addFilesToCache(files, group))
                .then(() => this.saveDirtyManifests())
                .then(() => this.running = false);
        }
        selectGroup(fileCount) {
            if (this.lastGroup >= 0 && this.lastGroupUsed < 50) {
                this.lastGroupUsed += fileCount;
                return this.lastGroup;
            }
            let min = Number.MAX_VALUE;
            let j;
            for (let i = 0; i < GROUP_COUNT; i++) {
                if (this.cacheGroups[i] < min - 50) {
                    min = this.cacheGroups[i];
                    j = i;
                }
            }
            this.lastGroup = j;
            this.lastGroupUsed = fileCount;
            return j;
        }
        addFilesToCache(files, group) {
            for (let { url, tempFilePath, size } of files) {
                let info = this.fileCache.get(url);
                if (info) {
                    this.cacheGroups[info.group]--;
                    this.totalFileSize -= info.size;
                    this.fileCache.delete(url);
                    info.accessTime = performance.now();
                    info.size = size;
                }
                else {
                    info = {
                        group,
                        url,
                        size,
                        fileName: Laya.Utils.getBaseName(tempFilePath),
                        accessTime: performance.now()
                    };
                }
                this.fileCache.set(url, info);
                this.cacheGroups[info.group]++;
                this.totalFileSize += size;
            }
            return this.saveManifest(group).then(success => {
                if (!success)
                    return;
                return Laya.Utils.runTasks(files, 5, ({ url, tempFilePath }) => {
                    let info = this.fileCache.get(url);
                    let saveFilePath = `${this.cacheRoot}/${group}/${info.fileName}`;
                    return Laya.PAL.fs.copyFile(tempFilePath, saveFilePath)
                        .catch(err => {
                        let msg = Laya.getErrorMsg(err);
                        console.warn("[Cache]create cache file", msg);
                        if (msg.indexOf("the maximum size of the file storage") !== -1) {
                            this.toClear |= 1;
                        }
                    });
                });
            });
        }
        clearSpace(sizeToClear) {
            if (sizeToClear < 0)
                return Promise.resolve();
            sizeToClear += MgCacheManager.minClearSpace;
            let allFiles = Array.from(this.fileCache.values());
            allFiles.sort((a, b) => a.accessTime - b.accessTime);
            let t = performance.now();
            let info = [0, 0];
            return this.doClearSpace(allFiles, sizeToClear, 0, info).then(() => {
                console.log(`[Cache]cleared ${info[0]} files/${info[1]} bytes in ${performance.now() - t}ms`);
            });
        }
        doClearSpace(allFiles, sizeToClear, round, outInfo) {
            let sizeCleared = 0;
            let i = 0;
            let n = allFiles.length;
            for (; i < n; i++) {
                let info = allFiles[i];
                sizeCleared += info.size;
                if (sizeCleared >= sizeToClear)
                    break;
            }
            let arr = allFiles.splice(0, i + 1);
            sizeCleared = 0;
            return Laya.Utils.runTasks(arr, 20, (info) => {
                this.fileCache.delete(info.url);
                this.totalFileSize -= info.size;
                this.cacheGroups[info.group]--;
                this.toSaveManifestFlags[info.group] = true;
                let fielName = `${this.cacheRoot}/${info.group}/${info.fileName}`;
                return Laya.PAL.fs.unlink(fielName).then(() => {
                    sizeCleared += info.size;
                }).catch(err => {
                    let msg = Laya.getErrorMsg(err);
                    if (msg.indexOf("no such file") === -1)
                        console.error("[Cache]delete cache file", msg);
                });
            }).then(() => {
                outInfo[0] += arr.length;
                outInfo[1] += sizeCleared;
                if (sizeCleared < sizeToClear && allFiles.length > 0 && round < 10)
                    return this.doClearSpace(allFiles, sizeToClear - sizeCleared, ++round, outInfo);
                else
                    return null;
            });
        }
        doClearAllCache() {
            return Laya.PAL.fs.rmdir(this.cacheRoot, { recursive: true }).catch(err => {
                console.warn("[Cache]failed to delete cache folder", Laya.getErrorMsg(err));
            }).then(() => this.createCacheDirs()).then(() => {
                this.fileCache.clear();
                this.cacheGroups.fill(0);
                this.totalFileSize = 0;
                this.toSaveManifestFlags.fill(false);
            });
        }
        loadAllManifests() {
            return Laya.PAL.fs.readdir(this.cacheRoot).then(files => {
                return Promise.all(files.map(fileName => {
                    if (fileName.startsWith("manifest-")) {
                        let group = parseInt(fileName.substring(9, fileName.length - 4));
                        if (!isNaN(group) && group >= 0 && group < GROUP_COUNT) {
                            return this.loadManifest(group);
                        }
                    }
                    return Promise.resolve();
                }));
            });
        }
        loadManifest(group) {
            return Laya.PAL.fs.readFile(`${this.cacheRoot}/manifest-${group}.bin`).then((data) => {
                let bytes = new Laya.Byte(data);
                bytes.readInt16();
                let url;
                let fileName;
                let accessTime;
                let size;
                let fileCnt = 0;
                let bytesTotal = 0;
                while (bytes.bytesAvailable > 0) {
                    let pos = bytes.pos;
                    let len = bytes.readUint32();
                    url = bytes.readUTFString();
                    fileName = bytes.readUTFString();
                    accessTime = bytes.readUint32();
                    size = bytes.readUint32();
                    bytes.pos = pos + len;
                    let info = {
                        group,
                        url,
                        fileName,
                        accessTime,
                        size
                    };
                    this.fileCache.set(url, info);
                    bytesTotal += size;
                    fileCnt++;
                }
                this.cacheGroups[group] = fileCnt;
                this.totalFileSize += bytesTotal;
                console.log(`[Cache]load manifest-${group} ${fileCnt}(files)/${bytesTotal}(bytes)`);
            }).catch(err => {
                console.error(`[Cache]load manifest-${group}`, Laya.getErrorMsg(err));
            });
        }
        saveDirtyManifests() {
            return Promise.all(this.toSaveManifestFlags.filter(needSave => needSave)
                .map((_, index) => this.saveManifest(index)));
        }
        saveManifest(group) {
            let bytes = new Laya.Byte();
            bytes.writeInt16(1);
            let fileCnt = 0;
            let bytesTotal = 0;
            for (let info of this.fileCache.values()) {
                if (info.group === group) {
                    let pos = bytes.pos;
                    bytes.writeUint32(0);
                    bytes.writeUTFString(info.url);
                    bytes.writeUTFString(info.fileName);
                    bytes.writeUint32(info.accessTime);
                    bytes.writeUint32(info.size);
                    let writePos = pos;
                    pos = bytes.pos;
                    bytes.pos = writePos;
                    bytes.writeUint32(pos - writePos);
                    bytes.pos = pos;
                    fileCnt++;
                    bytesTotal += info.size;
                }
            }
            return Laya.PAL.fs.writeFile(`${this.cacheRoot}/manifest-${group}.bin`, bytes.buffer).then(() => {
                this.toSaveManifestFlags[group] = false;
                console.log(`[Cache]save manifest-${group} ${fileCnt}(files)/${bytesTotal}(bytes)`);
                return true;
            }).catch(err => {
                let msg = Laya.getErrorMsg(err);
                console.error(`[Cache]save manifest-${group}`, msg);
                if (msg.indexOf("the maximum size of the file storage") !== -1) {
                    this.toClear |= 1;
                }
                return false;
            });
        }
        createCacheDirs() {
            return Promise.all(this.cacheGroups.map((_, index) => {
                let path = `${this.cacheRoot}/${index}`;
                return Laya.PAL.fs.exists(path).then(exists => {
                    if (!exists)
                        return Laya.PAL.fs.mkdir(path, { recursive: true }).catch(err => {
                            console.error("[Cache]failed to create cache dir", Laya.getErrorMsg(err));
                        });
                    else
                        return Promise.resolve();
                });
            }));
        }
        checkAndDeleteOldCacheDir() {
            let oldCacheDir = this.cacheRoot.substring(0, this.cacheRoot.lastIndexOf("/")) + "/layaairGame";
            return Laya.PAL.fs.exists(oldCacheDir).then(oldExists => {
                if (oldExists) {
                    console.log("[Cache]delete old cache folder");
                    return Laya.PAL.fs.rmdir(oldCacheDir, { recursive: true }).catch(err => {
                        console.warn("[Cache]failed to delete old cache folder", Laya.getErrorMsg(err));
                    });
                }
                else
                    return Promise.resolve();
            });
        }
    }
    MgCacheManager.minClearSpace = (5 * 1024 * 1024);
    MgCacheManager.spaceLimit = (200 * 1024 * 1024);
    MgCacheManager.processInterval = 2000;
    MgCacheManager.saveAccessTimeInterval = 15000;

    class MgDownloader extends Laya.Downloader {
        constructor(enableCache = true) {
            super();
            this.escapeZhCharsInURL = true;
            this.supportSubPackageMultiLevelFolders = true;
            let old = Laya.URL.postFormatURL;
            Laya.URL.postFormatURL = url => {
                url = this.checkSubpackagePrefix(url);
                return old.call(this, url);
            };
            if (Laya.Browser.onVVMiniGame || Laya.Browser.onQGMiniGame)
                this.supportSubPackageMultiLevelFolders = false;
            if (Laya.Browser.onWXMiniGame || Laya.Browser.onHWMiniGame || Laya.Browser.onTTMiniGame)
                this.escapeZhCharsInURL = false;
            if (enableCache) {
                let cacheRoot;
                if (Laya.Browser.onVVMiniGame)
                    cacheRoot = "internal://files/layaCache";
                else
                    cacheRoot = Laya.PAL.g.env.USER_DATA_PATH + "/layaCache";
                this.cacheManager = new MgCacheManager(cacheRoot);
            }
        }
        common(owner, url, originalUrl, contentType, onProgress, onComplete) {
            if (!url.startsWith("http://") && !url.startsWith("https://")) {
                if (contentType === "filePath")
                    onComplete(url);
                else
                    this.readFile(url, contentType, onComplete);
                return;
            }
            Promise.resolve().then(() => {
                if (this.cacheManager)
                    return this.cacheManager.getFile(url);
                else
                    return Promise.resolve(null);
            }).then(cacheFilePath => {
                if (cacheFilePath) {
                    if (contentType === "filePath")
                        onComplete(cacheFilePath);
                    else
                        this.readFile(cacheFilePath, contentType, onComplete);
                }
                else {
                    this.downloadFile(url, onProgress, (filePath, error) => {
                        if (filePath) {
                            if (contentType === "filePath")
                                onComplete(filePath);
                            else
                                this.readFile(filePath, contentType, onComplete);
                        }
                        else
                            onComplete(null, error);
                    });
                }
            });
        }
        image(owner, url, originalUrl, onProgress, onComplete) {
            let skipCache = false;
            if (Laya.Browser.onTBMiniGame) {
                if (window.__NOT_TBMINIGAME__ !== undefined) {
                    skipCache = window.__NOT_TBMINIGAME__;
                }
            }
            if (skipCache) {
                if (url.startsWith("http://") || url.startsWith("https://")) {
                    super.image(owner, url, originalUrl, onProgress, onComplete);
                }
                else {
                    super.image(owner, this.escapeURL(url), originalUrl, onProgress, onComplete);
                }
                return;
            }
            if (!url.startsWith("http://") && !url.startsWith("https://") || !this.cacheManager) {
                super.image(owner, this.escapeURL(url), originalUrl, onProgress, onComplete);
                return;
            }
            this.cacheManager.getFile(url).then(cacheFilePath => {
                if (cacheFilePath)
                    super.image(owner, cacheFilePath, originalUrl, onProgress, onComplete);
                else {
                    this.downloadFile(url, onProgress, (filePath, error) => {
                        if (filePath)
                            super.image(owner, filePath, originalUrl, onProgress, onComplete);
                        else
                            onComplete(null, error);
                    });
                }
            });
        }
        package(path, onProgress, onComplete) {
            let packageName = path;
            if (!this.supportSubPackageMultiLevelFolders) {
                packageName = path.replace(/\//g, ".");
                if (packageName !== path) {
                    if (!this.subPackages)
                        this.subPackages = {};
                    this.subPackages[path] = packageName;
                }
            }
            let loadSubpackageParams = {
                success: () => {
                    onComplete({ loadScript: false });
                },
                fail: (err) => {
                    onComplete({ loadScript: false }, Laya.getErrorMsg(err));
                },
                complete: null
            };
            if (Laya.Browser.onHWMiniGame) {
                loadSubpackageParams.subpackage = packageName;
            }
            else {
                loadSubpackageParams.name = packageName;
            }
            let loadTask = Laya.PAL.g.loadSubpackage(loadSubpackageParams);
            onProgress && loadTask.onProgressUpdate && loadTask.onProgressUpdate(res => onProgress(res.progress));
        }
        downloadFile(url, onProgress, onComplete) {
            let task = Laya.PAL.g.downloadFile({
                url: this.escapeURL(url),
                success: (res) => {
                    if (res.statusCode == null || res.statusCode === 200) {
                        let filePath = res.tempFilePath || res.apFilePath;
                        if (this.cacheManager && url.indexOf("?v=") === -1)
                            this.cacheManager.addFile(url, filePath);
                        onComplete(filePath);
                    }
                    else {
                        onComplete(null, Laya.getErrorMsg(res));
                    }
                },
                fail: (err) => onComplete(null, Laya.getErrorMsg(err))
            });
            if (onProgress && task && task.onProgressUpdate) {
                task.onProgressUpdate((res) => {
                    onProgress(res.progress);
                });
            }
        }
        readFile(url, contentType, onComplete) {
            let filePath = this.urlToFilePath(url);
            Laya.PAL.fs.readFile(filePath, contentType === "arraybuffer" ? null : "utf8").then(data => {
                switch (contentType) {
                    case "json":
                        onComplete(JSON.parse(data));
                        break;
                    case "xml":
                        onComplete(new Laya.XML(data));
                        break;
                    default:
                        onComplete(data);
                        break;
                }
            }).catch(err => onComplete(null, Laya.getErrorMsg(err)));
        }
        urlToFilePath(url) {
            let i = url.lastIndexOf("?");
            if (i != -1)
                return url.substring(0, i);
            else
                return url;
        }
        checkSubpackagePrefix(url) {
            if (!this.supportSubPackageMultiLevelFolders && this.subPackages) {
                for (let k in this.subPackages) {
                    if (url.startsWith(k)) {
                        url = this.subPackages[k] + url.substring(k.length);
                        break;
                    }
                }
            }
            return url;
        }
        escapeURL(url) {
            if (!this.escapeZhCharsInURL)
                return url;
            let str = "";
            let len = url.length;
            for (let i = 0; i < len; i++) {
                let word = url[i];
                if (IGNORE.test(word)) {
                    str += word;
                }
                else {
                    try {
                        str += encodeURI(word);
                    }
                    catch (e) {
                        console.warn("errorInfo", ">>>" + word);
                    }
                }
            }
            return str;
        }
    }
    const IGNORE = new RegExp("[-_.!~*'();/?:@&=+$,#%]|[0-9|A-Z|a-z]");

    class MgWebSocket {
        open(url, options) {
            let failed = false;
            this.ws = Laya.PAL.g.connectSocket(Object.assign({
                url,
                multiple: true,
                fail: (err) => {
                    failed = true;
                    this.onError(err);
                }
            }, options));
            if (this.ws == null || failed) {
                this.ws = null;
                return;
            }
            this.ws.onOpen(res => this.onOpen(res));
            this.ws.onClose(() => this.onClose());
            this.ws.onError(err => this.onError(err));
            this.ws.onMessage(msg => {
                if (msg.data) {
                    var data = msg.data;
                    if (data.isBuffer) {
                        data = this.base64ToArrayBuffer(data.data);
                    }
                    this.onMessage(data);
                }
            });
        }
        base64ToArrayBuffer(base64) {
            const binary = atob(base64);
            const len = binary.length;
            const bytes = new Uint8Array(len);
            for (let i = 0; i < len; i++) {
                bytes[i] = binary.charCodeAt(i);
            }
            return bytes.buffer;
        }
        close() {
            if (this.ws)
                this.ws.close({});
        }
        send(data) {
            if (this.ws == null)
                return Promise.reject("WebSocket is not open");
            return new Promise((resolve, reject) => {
                this.ws.send({
                    data,
                    success: () => resolve(),
                    fail: (e) => reject(e)
                });
            });
        }
    }

    class MgBrowserAdapter extends Laya.BrowserAdapter {
        constructor() {
            super(...arguments);
            this._visible = true;
            this._orientation = "portrait-primary";
        }
        init() {
            var _a;
            if (!console.time) {
                console.time = function (name) {
                };
                console.timeEnd = function (name) {
                    console.log(name);
                };
            }
            Laya.Browser.isDomSupported = false;
            (_a = MgBrowserAdapter.beforeInit) === null || _a === void 0 ? void 0 : _a.call(MgBrowserAdapter);
            this._supportSetCursor = Laya.PAL.hasAPI("setCursor");
            this._supportCreateArrayBufferURL = Laya.PAL.hasAPI("createBufferURL");
            if (Laya.PAL.hasAPI("connectSocket"))
                this.webSocketClass = MgWebSocket;
            else
                this.webSocketClass = null;
            let platform = "";
            let systemInfo = Laya.PAL.hasAPI("getSystemInfoSync") ? Laya.PAL.g.getSystemInfoSync() : null;
            if (systemInfo) {
                this._pixelRatio = systemInfo.pixelRatio;
                this._orientation = systemInfo.deviceOrientation === "landscape" ? "landscape-primary" : "portrait-primary";
                platform = systemInfo.platform || "";
            }
            else if (Laya.PAL.hasAPI("getWindowInfo")) {
                let windowInfo = Laya.PAL.g.getWindowInfo();
                this._pixelRatio = windowInfo.pixelRatio;
                if (Laya.PAL.g.getDeviceInfo) {
                    let deviceInfo = Laya.PAL.g.getDeviceInfo();
                    platform = deviceInfo.platform || "";
                }
            }
            if (Laya.Browser.onVVMiniGame || Laya.Browser.onQGMiniGame) {
                this._pixelRatio = window.devicePixelRatio;
            }
            this.setPlatform("", platform);
            systemInfo = systemInfo || {};
            const { SDKVersion } = Laya.PAL.hasAPI("getAppBaseInfo") ? Laya.PAL.g.getAppBaseInfo() : systemInfo;
            Laya.Browser.SDKVersion = SDKVersion || "";
            const { system } = Laya.PAL.hasAPI("getDeviceInfo") ? Laya.PAL.g.getDeviceInfo() : systemInfo;
            const systemVersionArr = system ? system.split(' ') : [];
            Laya.Browser.systemVersion = systemVersionArr.length ? systemVersionArr[systemVersionArr.length - 1] : '';
            if (Laya.Browser.onHWMiniGame) {
                this._pixelRatio = 1;
            }
            else {
                if (this._pixelRatio === 1 && Laya.Browser.onPC && !Laya.Browser.onDevTools)
                    this._pixelRatio = 2;
            }
            Laya.PAL.g.onShow && Laya.PAL.g.onShow(() => {
                this._visible = true;
                this.event(Laya.Event.VISIBILITY_CHANGE, true);
                this.event(Laya.Event.FOCUS);
            });
            Laya.PAL.g.onHide && Laya.PAL.g.onHide(() => {
                this._visible = false;
                this.event(Laya.Event.VISIBILITY_CHANGE, false);
                this.event(Laya.Event.BLUR);
            });
            if (Laya.PAL.hasAPI("onWindowResize")) {
                Laya.PAL.g.onWindowResize(result => {
                    this.event(Laya.Event.RESIZE);
                });
            }
        }
        start() {
            var _a;
            let downloader = Laya.Loader.downloader = new MgDownloader(Laya.PAL.hasAPI("getFileSystemManager") && Laya.PAL.hasAPI(Laya.PAL.g.getFileSystemManager(), "writeFile") && Laya.PAL.hasAPI(Laya.PAL.g.getFileSystemManager(), "readdir"));
            this.setupWasmSupport();
            (_a = MgBrowserAdapter.afterInit) === null || _a === void 0 ? void 0 : _a.call(MgBrowserAdapter);
            if (downloader.cacheManager)
                return downloader.cacheManager.start();
            else
                return Promise.resolve();
        }
        onInitRender() {
            if (Laya.Browser.onTBMiniGame) {
                Laya.LayaGL.renderEngine._supportCapatable.turnOffSRGB();
            }
            if (Laya.Browser.onAlipayMiniGame) {
                Laya.LayaGL.renderEngine._supportCapatable.turnOffSRGB();
                Laya.LayaGL.renderEngine._supportCapatable.turnOffCapableAndExtension(Laya.RenderCapable.MSAA, null);
            }
            if (Laya.Browser.onTBMiniGame) {
                if (!Laya.PAL.g.isIDE) {
                    let gl = Laya.LayaGL.renderEngine._context;
                    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
                }
            }
            if (Laya.Browser.onHWMiniGame) {
                Laya.LayaGL.textureContext.needBitmap = false;
            }
        }
        setupWasmSupport() {
            let wasmGlobal;
            if (Laya.Browser.onWXMiniGame)
                wasmGlobal = window.WXWebAssembly;
            else if (Laya.Browser.onAlipayMiniGame)
                wasmGlobal = window.MYWebAssembly;
            else if (Laya.Browser.onTTMiniGame)
                wasmGlobal = window.TTWebAssembly;
            else if (Laya.Browser.onHWMiniGame)
                wasmGlobal = window.qg;
            if (wasmGlobal) {
                if (!window.WebAssembly) {
                    try {
                        window.WebAssembly = { Memory: wasmGlobal.Memory };
                    }
                    catch (e) {
                    }
                }
                Laya.WasmAdapter.Memory = wasmGlobal.Memory;
                Laya.WasmAdapter.instantiateWasm = (wasmFile, imports) => {
                    wasmFile = Laya.WasmAdapter.locateFileDefault(wasmFile);
                    return wasmGlobal.instantiate(wasmFile, imports);
                };
            }
            else if (window.WebAssembly) {
                let shouldInit = Laya.PAL.g.setWasmTaskCompile != null;
                Laya.WasmAdapter.instantiateWasm = (wasmFile, imports) => {
                    wasmFile = Laya.WasmAdapter.locateFileDefault(wasmFile);
                    return Laya.Laya.loader.fetch(wasmFile, "arraybuffer").then(data => {
                        if (data) {
                            if (shouldInit) {
                                shouldInit = false;
                                Laya.PAL.g.setWasmTaskCompile(true);
                            }
                            return window.WebAssembly.instantiate(data, imports);
                        }
                        else {
                            console.error("WASM file not found: " + wasmFile);
                            return null;
                        }
                    });
                };
            }
        }
        getVisibility() {
            return this._visible;
        }
        getScreenOrientation() {
            return this._orientation;
        }
        createMainCanvas() {
            let canvas;
            if (Laya.Browser.onTBMiniGame) {
                canvas = window.screencanvas
                    || window.canvas.getRealCanvas();
            }
            else {
                canvas = window.canvas || window.__canvas;
            }
            canvas.id = "layaCanvas";
            return canvas;
        }
        createElement(tagName) {
            var _a;
            let ele;
            if (tagName === "canvas" && typeof (Laya.PAL.g.createCanvas) === "function") {
                if (Laya.Browser.onTBMiniGame && window.__NOT_TBMINIGAME__) {
                    ele = window.canvas.getRealCanvas();
                }
                else {
                    ele = Laya.PAL.g.createCanvas();
                }
            }
            else {
                ele = super.createElement(tagName);
            }
            if (!ele.style)
                ele.style = {};
            else if (ele.style === ((_a = window.canvas) === null || _a === void 0 ? void 0 : _a.style))
                ele.style = {};
            return ele;
        }
        getElementById(id) {
            if (window.document.getElementById) {
                return window.document.getElementById(id);
            }
            else {
                Laya.PAL.warnIncompatibility("getElementById");
                return null;
            }
        }
        removeElement(ele) {
            if (ele.remove) {
                ele.remove();
            }
            else if (ele.dispose) {
                ele.dispose();
            }
            else {
                ele = null;
            }
        }
        setCursor(cursor) {
            if (!this._supportSetCursor)
                return;
            let arr = cursor.split(" ");
            let x = arr[1] ? parseInt(arr[1].trim()) : 0;
            let y = arr[2] ? parseInt(arr[2].trim()) : 0;
            let i = arr[0].indexOf("url(");
            if (i != -1) {
                let j = arr[0].indexOf(")");
                if (j != -1)
                    arr[0] = arr[0].substring(i + 4, j);
            }
            if (isNaN(x) || isNaN(y))
                x = y = undefined;
            Laya.PAL.g.setCursor(arr[0], x, y);
        }
        get supportArrayBufferURL() {
            return this._supportCreateArrayBufferURL;
        }
        createBufferURL(data) {
            return Laya.PAL.g.createBufferURL(data);
        }
        revokeBufferURL(url) {
            return Laya.PAL.g.revokeBufferURL(url);
        }
        getOpenDataContextCanvas() {
            return window.sharedCanvas;
        }
        postMessageToOpenDataContext(msg) {
            if (Laya.PAL.g.getOpenDataContext)
                Laya.PAL.g.getOpenDataContext().postMessage(msg);
        }
        onCaptureGlobalError(enabled, func) {
            if (enabled) {
                if (Laya.PAL.hasAPI("onError"))
                    Laya.PAL.g.onError(func);
                if (Laya.PAL.g.onUnhandledRejection)
                    Laya.PAL.g.onUnhandledRejection(func);
            }
            else {
                if (Laya.PAL.hasAPI("offError"))
                    Laya.PAL.g.offError(func);
                if (Laya.PAL.g.offUnhandledRejection)
                    Laya.PAL.g.offUnhandledRejection(func);
            }
        }
        alert(msg) {
            if (typeof (window.alert) === "function") {
                window.alert.call(null, msg);
            }
            else {
                console.warn("alert is not a function");
            }
        }
    }
    Laya.PAL.register("browser", MgBrowserAdapter);

    class MgDeviceAdapter extends Laya.DeviceAdapter {
        constructor() {
            super();
            this._watchId = 1;
            this._watchDic = new Map();
            this._accInfo = { x: 0, y: 0, z: 0 };
            this._rotInfo = { alpha: 0, beta: 0, gamma: 0, absolute: false, compassAccuracy: 0 };
        }
        get supportedLocation() {
            return !!(Laya.PAL.g.getFuzzyLocation || Laya.PAL.g.getLocation);
        }
        getCurrentPosition(successCallback, errorCallback, options) {
            if (Laya.PAL.g.getFuzzyLocation)
                Laya.PAL.g.getFuzzyLocation({
                    type: 'gcj02',
                    success: (res) => {
                        successCallback({
                            latitude: res.latitude,
                            longitude: res.longitude,
                            timestamp: performance.now()
                        });
                    },
                    fail: (err) => {
                        errorCallback === null || errorCallback === void 0 ? void 0 : errorCallback({ code: 1, message: err.errMsg });
                    }
                });
            else {
                Laya.PAL.g.getLocation({
                    type: 'gcj02',
                    success: (res) => {
                        successCallback({
                            latitude: res.latitude,
                            longitude: res.longitude,
                            speed: res.speed,
                            altitude: res.altitude,
                            accuracy: res.accuracy,
                            timestamp: performance.now()
                        });
                    },
                    fail: (err) => {
                        errorCallback === null || errorCallback === void 0 ? void 0 : errorCallback({ code: 1, message: err.errMsg });
                    }
                });
            }
        }
        watchPosition(successCallback, errorCallback, options) {
            if (this._watchDic.size === 0) {
                Laya.ILaya.systemTimer.loop(1000, this, this.onUpdate);
                this._watchOptions = options;
            }
            this._watchId++;
            this._watchDic.set(this._watchId, { successCallback, errorCallback });
            return this._watchId;
        }
        clearWatchPosition(id) {
            this._watchDic.delete(id);
            if (this._watchDic.size === 0) {
                Laya.ILaya.systemTimer.clear(this, this.onUpdate);
                this._watchOptions = null;
            }
        }
        onUpdate() {
            let callbacks = Array.from(this._watchDic.values());
            this.getCurrentPosition(info => callbacks.forEach(callback => callback.successCallback(info)), err => callbacks.forEach(callback => { var _a; return (_a = callback.errorCallback) === null || _a === void 0 ? void 0 : _a.call(callback, err); }), this._watchOptions);
        }
        startListeningDeviceMotion() {
            Laya.PAL.g.startAccelerometer({ interval: "game" });
            Laya.PAL.g.onAccelerometerChange(res => {
                Object.assign(this._accInfo, res);
                this.event("devicemotion", [this._accInfo, this._accInfo, {}, 0]);
            });
        }
        startListeningDeviceOrientation() {
            Laya.PAL.g.startGyroscope({ interval: "game" });
            Laya.PAL.g.onGyroscopeChange(res => {
                this._rotInfo.alpha = res.z;
                this._rotInfo.beta = res.x;
                this._rotInfo.gamma = res.y;
                this.event("deviceorientation", [true, this._rotInfo]);
            });
        }
    }
    Laya.PAL.register("device", MgDeviceAdapter);

    class MgFileSystemAdapter extends Laya.FileSystemAdapter {
        constructor() {
            super();
            this.hasAccess = false;
            this.fs = Laya.PAL.g.getFileSystemManager();
            this.hasAccess = Laya.PAL.hasAPI(this.fs, "access");
        }
        readFile(path, encoding) {
            return new Promise((resolve, reject) => {
                var _a;
                this.fs.readFile({
                    filePath: path,
                    encoding: (_a = encoding) !== null && _a !== void 0 ? _a : undefined,
                    success: (res) => resolve(res.data),
                    fail: (err) => reject(err)
                });
            });
        }
        writeFile(path, data, encoding) {
            return new Promise((resolve, reject) => {
                var _a;
                this.fs.writeFile({
                    filePath: path,
                    data: data,
                    encoding: (_a = encoding) !== null && _a !== void 0 ? _a : undefined,
                    success: () => resolve(),
                    fail: (err) => reject(err)
                });
            });
        }
        unlink(path) {
            return new Promise((resolve, reject) => {
                this.fs.unlink({
                    filePath: path,
                    success: () => resolve(),
                    fail: (err) => reject(err)
                });
            });
        }
        copyFile(srcPath, destPath) {
            return new Promise((resolve, reject) => {
                this.fs.copyFile({
                    srcPath,
                    destPath,
                    success: () => resolve(),
                    fail: (err) => reject(err)
                });
            });
        }
        exists(path) {
            return new Promise(resolve => {
                if (this.hasAccess) {
                    this.fs.access({
                        path,
                        success: () => resolve(true),
                        fail: (err) => resolve(false)
                    });
                }
                else {
                    this.fs.getFileInfo({
                        filePath: path,
                        success: (res) => resolve(true),
                        fail: (err) => resolve(false)
                    });
                }
            });
        }
        getFileSize(path) {
            return new Promise((resolve, reject) => {
                this.fs.getFileInfo({
                    filePath: path,
                    success: (res) => resolve(res.size),
                    fail: (err) => reject(err)
                });
            });
        }
        mkdir(path, options) {
            return new Promise((resolve, reject) => {
                this.fs.mkdir({
                    dirPath: path,
                    recursive: options === null || options === void 0 ? void 0 : options.recursive,
                    success: () => resolve(),
                    fail: (err) => reject(err)
                });
            });
        }
        rmdir(path, options) {
            try {
                this.fs.rmdirSync(path, options === null || options === void 0 ? void 0 : options.recursive);
                return Promise.resolve();
            }
            catch (e) {
                return Promise.reject(e);
            }
        }
        readdir(path) {
            return new Promise((resolve, reject) => {
                this.fs.readdir({
                    dirPath: path,
                    success: (res) => resolve(res.files),
                    fail: (err) => reject(err)
                });
            });
        }
        unzip(zipFilePath, targetPath) {
            return new Promise((resolve, reject) => {
                this.fs.unzip({
                    zipFilePath,
                    targetPath,
                    success: () => resolve(),
                    fail: (err) => reject(err)
                });
            });
        }
    }
    Laya.PAL.register("fs", MgFileSystemAdapter);

    class MgFontAdapter extends Laya.FontAdapter {
        loadFont(task) {
            if (!Laya.PAL.g.loadFont) {
                Laya.PAL.warnIncompatibility("TTFont");
                return Promise.resolve(null);
            }
            return task.loader.fetch(task.url, "filePath", task.progress.createCallback(), task.options).then((filePath) => {
                if (filePath) {
                    let fontFamily = Laya.PAL.g.loadFont(filePath);
                    return fontFamily ? { family: fontFamily } : null;
                }
                else
                    return null;
            });
        }
    }
    Laya.PAL.register("font", MgFontAdapter);

    class MgInnerAudioChannel extends Laya.SoundChannel {
        get position() {
            if (this._ctx)
                return this._ctx.currentTime;
            else
                return 0;
        }
        get duration() {
            if (this._ctx)
                return this._ctx.duration;
            else
                return 0;
        }
        onPlay(url) {
            Laya.Laya.loader.fetch(url, "filePath").then((filePath) => this.onLoaded(filePath));
        }
        onLoaded(filePath) {
            if (!this._started || filePath == null)
                return;
            this._loaded = true;
            let ctx = this._ctx = this.createContext();
            ctx.onError(err => {
                console.error("MgInnerAudioChannel: " + Laya.getErrorMsg(err));
                this.stop();
            });
            ctx.onEnded(() => this.onPlayEnd());
            let playSound = () => {
                if (this._ctx && !this._paused) {
                    if (this.startTime != 0)
                        ctx.seek(this.startTime);
                    ctx.play();
                }
                ctx.offCanplay(playSound);
            };
            ctx.onCanplay(playSound);
            ctx.src = filePath;
            ctx.playbackRate = this.playbackRate;
            ctx.loop = this.loops === 0;
            ctx.volume = this._muted ? 0 : this._volume;
        }
        onPlayAgain() {
            if (this.startTime != 0)
                this._ctx.seek(this.startTime);
            this._ctx.play();
        }
        onStop() {
            this.releaseContext();
        }
        onPause() {
            this._ctx.pause();
        }
        onResume() {
            this._ctx.play();
        }
        onVolumeChanged() {
            this._ctx.volume = this._muted ? 0 : this._volume;
        }
        onMuted() {
            if (this._muted)
                this._ctx.pause();
            else
                this._ctx.play();
        }
        createContext() {
            return Laya.PAL.g.createInnerAudioContext();
        }
        releaseContext() {
            var _a;
            (_a = this._ctx) === null || _a === void 0 ? void 0 : _a.destroy();
            this._ctx = null;
        }
    }

    class MgVideoPlayer extends Laya.VideoPlayerBackend {
        constructor() {
            super(...arguments);
            this._loop = false;
            this._ended = false;
            this._muted = false;
            this._playbackRate = 1;
        }
        get loop() {
            return this._loop;
        }
        set loop(value) {
            this._loop = value;
            if (this.video)
                this.video.loop = value;
        }
        get ended() {
            return this._ended;
        }
        get currentTime() {
            return this._currentTime;
        }
        set currentTime(value) {
            if (this.video)
                this.video.seek(value * 1000);
        }
        get muted() {
            return this._muted;
        }
        set muted(value) {
            this._muted = value;
            if (this.video)
                this.video.muted = value;
        }
        get playbackRate() {
            return this._playbackRate;
        }
        set playbackRate(value) {
            this._playbackRate = value;
            if (this.video)
                this.video.playbackRate = value;
        }
        onLoad(url) {
            this._ended = false;
            if (this._loaded)
                this.video.destroy();
            this.video = Laya.PAL.g.createVideo(Object.assign({}, this.options, this.getNodeTransform(), {
                src: Laya.URL.postFormatURL(Laya.URL.formatURL(url)),
                autoplay: this._playing,
                loop: this._loop,
                muted: this._muted,
                playbackRate: this._playbackRate,
            }));
            this.video.onEnded(() => this._ended = true);
            this.video.onError((err) => {
                console.error("MgVideoPlayer: " + Laya.getErrorMsg(err));
            });
            this.setLoaded();
        }
        onPlay() {
            this.video.play();
        }
        onPause() {
            this.video.pause();
        }
        onTransformChanged() {
            if (!this.video)
                return;
            let { x, y, width, height } = this.getNodeTransform();
            if (this.video.paintTo) {
                this.video.paintTo(Laya.Browser.mainCanvas.source, x, y, 0, 0, width, height);
            }
            else {
                this.video.x = x;
                this.video.y = y;
                this.video.width = width;
                this.video.height = height;
            }
        }
        onDestroy() {
            this.video.destroy();
        }
    }

    class MgWebAudioChannel extends MgInnerAudioChannel {
        constructor(url) {
            super(url);
        }
        createContext() {
            return Laya.PAL.g.createInnerAudioContext({ useWebAudioImplement: true });
        }
    }

    class MgMediaAdapter extends Laya.MediaAdapter {
        init() {
            if (Laya.PAL.g.createWebAudioContext)
                this.audioCtx = Laya.PAL.g.createWebAudioContext();
            else if (Laya.PAL.g.getAudioContext)
                this.audioCtx = Laya.PAL.g.getAudioContext();
            this.longAudioClass = MgInnerAudioChannel;
            this.shortAudioClass = MgWebAudioChannel;
            this.videoPlayerClass = Laya.PAL.hasAPI("createVideo") ? MgVideoPlayer : null;
            this.videoTextureClass = null;
        }
    }
    Laya.PAL.register("media", MgMediaAdapter);

    class MgStorageAdapter extends Laya.StorageAdapter {
        checkSupport() {
            return Laya.PAL.hasAPI("getStorageInfoSync");
        }
    }
    Laya.PAL.register("storage", MgStorageAdapter);

    class MgTextInputAdapter extends Laya.TextInputAdapter {
        constructor() {
            super();
            this._editInline = false;
            MgTextInputAdapter.enabled = Laya.PAL.hasAPI("onKeyboardInput");
            if (MgTextInputAdapter.enabled) {
                Laya.PAL.g.onKeyboardInput(this.onKeyboardInput.bind(this));
                Laya.PAL.g.onKeyboardConfirm(this.onKeyboardConfirm.bind(this));
                Laya.PAL.g.onKeyboardComplete(this.onKeyboardComplete.bind(this));
            }
        }
        setText(value) {
            if (!MgTextInputAdapter.enabled)
                return;
            Laya.PAL.g.updateKeyboard({ value });
        }
        onBegin() {
            return Promise.resolve();
        }
        onCanShowKeyboard() {
            let target = this.target;
            if (!target.editable || !MgTextInputAdapter.enabled)
                return Promise.resolve();
            return new Promise((resolve, reject) => {
                Laya.PAL.g.showKeyboard({
                    defaultValue: target.text,
                    maxLength: target.maxChars <= 0 ? 1E5 : target.maxChars,
                    multiple: target.multiline,
                    confirmHold: true,
                    confirmType: target.confirmType,
                    keyboardType: 'text',
                    success: resolve,
                    fail: reject
                });
            });
        }
        onEnd(target, complete, switching) {
            if (complete || switching || !MgTextInputAdapter.enabled)
                return Promise.resolve();
            return new Promise((resolve, reject) => {
                Laya.PAL.g.hideKeyboard({ success: resolve, fail: reject });
            });
        }
        onKeyboardInput(ev) {
            if (!this.target)
                return;
            let str = this.validateText(ev.value);
            if (this.updateTargetText(str))
                this.target.event(Laya.Event.INPUT);
        }
        onKeyboardConfirm(ev) {
            if (!this.target)
                return;
            this.onKeyboardInput(ev);
            this.target.event(Laya.Event.ENTER);
            this.end();
        }
        onKeyboardComplete(ev) {
            this.end(true);
        }
    }
    MgTextInputAdapter.enabled = true;
    Laya.PAL.register("textInput", MgTextInputAdapter);

    class WxVideoTexture extends Laya.VideoTexture {
        constructor() {
            super();
            this._ended = false;
            this._waitFirstFrame = false;
            this.decoder = Laya.PAL.g.createVideoDecoder({
                type: "wemedia"
            });
            this.decoder.on("frame", (res) => {
                this._currentTime = res.pts / 1000;
                if (this._waitFirstFrame) {
                    this._waitFirstFrame = false;
                    if (!this._playing) {
                        this.render(true);
                        this.decoder.wait(true);
                    }
                }
            });
            this.decoder.on("ended", () => {
                if (this._loop)
                    this.decoder.stop().then(() => this.decoder.start(this._startOption));
                else {
                    this._ended = true;
                    this.event("ended");
                }
            });
        }
        get readyState() {
            return this._loaded ? 1 : 0;
        }
        get ended() {
            return this._ended;
        }
        get currentTime() {
            return this._currentTime;
        }
        set currentTime(value) {
            this.decoder.seek(value * 1000);
        }
        onLoad(url) {
            let src = this._source;
            this._ended = false;
            this._waitFirstFrame = false;
            if (this._loaded)
                this.decoder.stop();
            this._loaded = false;
            if (this._source !== src)
                return;
            this._startOption = {};
            this._startOption.source = Laya.URL.postFormatURL(Laya.URL.formatURL(url));
            if (Laya.Browser.isIOSHighPerformanceModePlus)
                this._startOption.videoDataType = 2;
            this.decoder.start(this._startOption).then(res => {
                this.setLoaded(res.width, res.height, true);
                if (!this._playing)
                    this._waitFirstFrame = true;
            }).catch(err => {
                console.warn("MgVideoTexture: " + err.message);
            });
        }
        onPlay() {
            this.decoder.wait(false);
        }
        onPause() {
            this.decoder.wait(true);
        }
        onStop() {
            this.decoder.stop();
        }
        onRender() {
            const frameData = this.decoder.getFrameData();
            if (frameData) {
                const { data } = frameData;
                Laya.LayaGL.textureContext.setTexturePixelsData(this._texture, new Uint8ClampedArray(data), false, false);
                return true;
            }
            else
                return false;
        }
        onDestroy() {
            this.decoder.remove();
        }
    }

    MgBrowserAdapter.beforeInit = function () {
        Laya.Browser.onWXMiniGame = true;
        Laya.Browser.onMiniGame = true;
        Laya.Browser.isIOSHighPerformanceMode = GameGlobal.isIOSHighPerformanceMode;
        Laya.Browser.isIOSHighPerformanceModePlus = GameGlobal.isIOSHighPerformanceModePlus;
        Laya.PAL.g = window.wx;
        Laya.PAL.g.willGenerateUndefinedAPIs = true;
    };
    MgBrowserAdapter.afterInit = function () {
        if (!Laya.Browser.onDevTools)
            Laya.PAL.media.videoTextureClass = WxVideoTexture;
    };

    exports.MgBrowserAdapter = MgBrowserAdapter;
    exports.MgCacheManager = MgCacheManager;
    exports.MgDeviceAdapter = MgDeviceAdapter;
    exports.MgDownloader = MgDownloader;
    exports.MgFileSystemAdapter = MgFileSystemAdapter;
    exports.MgFontAdapter = MgFontAdapter;
    exports.MgInnerAudioChannel = MgInnerAudioChannel;
    exports.MgMediaAdapter = MgMediaAdapter;
    exports.MgStorageAdapter = MgStorageAdapter;
    exports.MgTextInputAdapter = MgTextInputAdapter;
    exports.MgVideoPlayer = MgVideoPlayer;
    exports.MgWebAudioChannel = MgWebAudioChannel;
    exports.MgWebSocket = MgWebSocket;
    exports.WxVideoTexture = WxVideoTexture;

})(window.Laya = window.Laya || {}, Laya);
