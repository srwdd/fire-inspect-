// 消防监督检查智能辅助系统 — 扩展模块
// 语音搜索 + 拍照报告（从 app.js 提取，降低主文件复杂度）
const APP_EXTRAS = {
  // ═══ 拍照 + 报告 ═══
  async uploadPhoto(e) {
    const fileList = e.target.files;
    if (!fileList || fileList.length === 0) return;
    // 累积照片：首次或追加
    if (!this._pendingPhotos) this._pendingPhotos = [];
    for (let i = 0; i < fileList.length; i++) {
      this._pendingPhotos.push(fileList[i]);
    }
    this.photoUploadCount = this._pendingPhotos.length;
    await this._doUploadPhotos();
  },
  async _doUploadPhotos() {
    if (!this._pendingPhotos || this._pendingPhotos.length === 0) return;
    this.photoAnalyzing = true;
    try {
      const form = new FormData();
      for (let i = 0; i < this._pendingPhotos.length; i++) {
        form.append('files', this._pendingPhotos[i]);
      }
      form.append('item_index', this.currentIndex);
      const r = await API.post(`/${this.inspectionId}/photo`, form);
      this.photoResult = r.data.data?.analysis || { violation: null, reason: '分析完成', confidence: 0 };
      if (this.currentItem) {
        this.photoCompareHazard = this.getTypicalHazard(this.currentItem.facility);
      }
      // 置信度 < 0.5 → 建议再拍
      const conf = this.photoResult.confidence || 0;
      if (conf < 0.5 && this._pendingPhotos.length < 3) {
        this.photoLowConfidence = true;
      } else {
        this.photoLowConfidence = false;
      }
    } catch (e) {
      this.photoResult = { violation: null, reason: '分析失败: ' + e.message, confidence: 0 };
      this.photoCompareHazard = null;
      this.photoLowConfidence = false;
    }
    this.photoAnalyzing = false;
  },
  retakePhoto() {
    // 保留已有照片，重新打开相机追加拍摄
    this.photoLowConfidence = false;
    // 触发隐藏的 file input
    var input = document.getElementById('photo-input');
    if (input) {
      input.value = '';
      input.click();
    }
  },
  discardRetake() {
    // 放弃追加，使用当前结果
    this.photoLowConfidence = false;
    this._pendingPhotos = [];
  },
  confirmPhotoResult() {
    // AI 分析结果自动填表
    const a = this.photoResult || {};
    // violation: true=不合格, false=合格, null/undefined=AI无法判断
    if (a.violation === null || a.violation === undefined) {
      // AI 无法判断 — 不自动填表，关闭弹窗让用户手动判定
      this.showPhoto = false;
      this.photoResult = null;
      return;
    }
    this.judge(
      a.violation ? 'fail' : 'pass',
      a.suggested_note || a.reason || '',
      a.suggested_rectification_status || a.deadline || ''
    );
    this.showPhoto = false;
    this.photoResult = null;
    this._pendingPhotos = [];
    this.photoLowConfidence = false;
  },
  async uploadRecheckPhoto(e) {
    const file = e.target.files[0];
    if (!file) return;
    try {
      const form = new FormData();
      form.append('file', file);
      form.append('item_index', this.currentIndex);
      await API.post(`/${this.inspectionId}/photo`, form);
    } catch(e) { console.error(e); }
    const reader = new FileReader();
    var self = this;
    reader.onload = function(ev) {
      self.recheckPhoto = ev.target.result;
      // Also store in judgments for AI comparison
      if (!self.judgments[self.currentIndex]) self.judgments[self.currentIndex] = {};
      if (!self.judgments[self.currentIndex].photos) self.judgments[self.currentIndex].photos = [];
      self.judgments[self.currentIndex].photos.push(ev.target.result);
    };
    reader.readAsDataURL(file);
  },
  async viewReport() {
    try {
      const r = await API.get(`/${this.inspectionId}/report`);
      this.report = r.data.data;
      this.page = 'report';
    } catch (e) { alert('获取报告失败: ' + e.message); }
  },
  newInspection() { this.page = 'home'; this.ownerRpt = null; },
  async viewOwnerReport() {
    try {
      const r = await API.get(`/${this.inspectionId}/owner-report`);
      this.ownerRpt = r.data.data;
      this.page = 'ownerReport';
    } catch (e) { alert('获取业主报告失败: ' + e.message); }
  },
  printOwnerReport() {
    const el = document.getElementById('owner-print-area');
    if (!el) return;
    const win = window.open('', '_blank', 'width=800,height=600');
    win.document.write('<html><head><meta charset="UTF-8"><title>消防安全隐患整改告知书</title><link rel="stylesheet" href="styles.css"></head><body>' + el.innerHTML + '</body></html>');
    win.document.close();
    setTimeout(() => win.print(), 500);
  },

  // ═══ 语音搜索 ═══
  startSearch() { this.page = 'search'; this.searchResult = ''; this.searchQuery = ''; },
  async doSearch() {
    var q = this.searchQuery.trim();
    if (!q) return;
    this.searching = true; this.searchResult = ''; this.searchData = null;
    try {
      var api = axios.create({ baseURL: API_BASE.replace('/inspection', '/speech') });
      var r = await api.post('/search-all', { question: q });
      var d = r.data.data;
      this.searchData = d;
      this.searchResult = APP_EXTRAS._formatSearchResult(d);
    } catch (e) { this.searchResult = '查询失败: ' + (e.response?.data?.detail || e.message); }
    this.searching = false;
  },
  _formatSearchResult(d) {
    d = d || {};
    var regs = d.regulations || [], cases = d.cases || [], sols = d.solutions || [];
    var h = '<div class="result-tabs">';
    h += '<div class="result-tab"><div class="tab-title">\u{1f4d6} 法规依据（'+regs.length+'条）</div>';
    if (regs.length === 0) h += '<div class="tab-empty">暂无匹配法规</div>';
    else regs.slice(0,3).forEach(function(r,idx){ var cls=idx===0?'tab-item tab-item-first':'tab-item tab-item-sub'; h += '<div class="'+cls+'"><b>'+APP_EXTRAS._esc(r.title||'')+'</b><br><span class="tab-meta">'+APP_EXTRAS._esc(r.source||'')+' '+APP_EXTRAS._esc(r.article||'')+(r.penalty?' | ⚠️ '+APP_EXTRAS._esc(r.penalty):'')+'</span></div>'; }, this);
    h += '</div>';
    h += '<div class="result-tab"><div class="tab-title">\u{1f6a8} 相似案例（'+cases.length+'条）</div>';
    if (cases.length === 0) h += '<div class="tab-empty">暂无相似案例</div>';
    else cases.slice(0,2).forEach(function(c,idx){ var cls=idx===0?'tab-item tab-item-first':'tab-item tab-item-sub'; h += '<div class="'+cls+'"><b>'+APP_EXTRAS._esc(c.finding||'')+'</b><br><span class="tab-meta">'+APP_EXTRAS._esc(c.venue_type||'')+' | '+APP_EXTRAS._esc(c.cause||'')+(c.severity==='critical'?' | \u{1f534}严重':c.severity==='high'?' | \u{1f7e0}高风险':'')+'</span></div>'; }, this);
    h += '</div>';
    h += '<div class="result-tab"><div class="tab-title">\u{1f527} 整改方案（'+sols.length+'条）</div>';
    if (sols.length === 0) h += '<div class="tab-empty">暂无匹配方案</div>';
    else sols.slice(0,2).forEach(function(s,idx){ var cls=idx===0?'tab-item tab-item-first':'tab-item tab-item-sub'; h += '<div class="'+cls+'"><b>'+APP_EXTRAS._esc(s.immediate_action||'')+'</b><br><span class="tab-meta">期限：'+APP_EXTRAS._esc(s.rectification_period||'')+' | 责任人：'+APP_EXTRAS._esc(s.responsible_role||'')+(s.cost_estimate?' | \u{1f4b0}'+APP_EXTRAS._esc(s.cost_estimate):'')+'</span></div>'; }, this);
    h += '</div></div>';
    h += '<style>.tab-item-first{background:#fff5f5!important;border-left:3px solid #c41e3a!important;padding:8px 9px!important;border-radius:0 8px 8px 0!important;box-sizing:border-box!important}.tab-item-first b{font-size:15px!important;color:#c41e3a!important}.tab-item-sub{opacity:.75;font-size:12px}.tab-item-sub b{font-size:13px!important;color:#555!important}@media(max-width:480px){.tab-item-first b{font-size:14px!important}.tab-item-sub{font-size:11px}.tab-item-sub b{font-size:12px!important}}</style>'; return h;
  },
  _esc(s) { return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); },
  voiceAvailable() {
    var hasGUM = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
    var hasMR = typeof MediaRecorder !== 'undefined';
    var isSecure = location.protocol === 'https:' || location.hostname === 'localhost';
    var isIP = /^\d+\.\d+\.\d+\.\d+$/.test(location.hostname);
    this._voiceDiag = { getUserMedia: hasGUM, mediaRecorder: hasMR, secure: isSecure, isIP: isIP };
    return hasGUM && hasMR && isSecure;
  },
  voiceUnavailableReason() {
    var d = this._voiceDiag || {};
    if (!d.mediaRecorder) {
      var ua = navigator.userAgent;
      if (/MicroMessenger/.test(ua)) return '微信不支持录音，请用系统浏览器打开';
      if (/QQBrowser|MQQBrowser/.test(ua)) return 'QQ浏览器不支持录音，请用Chrome打开';
      if (/UCBrowser|UCWEB/.test(ua)) return 'UC浏览器不支持录音，请用Chrome打开';
      if (/Baidu|baiduboxapp/.test(ua)) return '百度浏览器不支持录音，请用Chrome打开';
      if (/MiuiBrowser/.test(ua)) return 'MIUI浏览器不支持录音，请用Chrome打开';
      if (/HuaweiBrowser|HUAWEI|HarmonyOS|ArkWeb/.test(ua)) return '鸿蒙自带浏览器不支持录音，请安装Chrome浏览器打开';
      if (/iPad|iPhone|iPod/.test(ua)) return 'iOS请使用Safari浏览器（需iOS 14.5+）';
      if (/Android/.test(ua) && /Chrome/.test(ua)) return 'Chrome版本过旧，请更新Chrome后重试';
      return '浏览器不支持录音，请用Chrome/Safari打开';
    }
    if (!d.secure) return '录音需要HTTPS连接';
    if (!d.getUserMedia) return '浏览器不支持麦克风访问';
    return '';
  },
  async startVoice() {
    if (this.isRecording) { this.stopVoice(); return; }
    if (!this.voiceAvailable()) { this.searchResult = '⚠️ ' + this.voiceUnavailableReason(); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      this._mediaStream = stream;
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : MediaRecorder.isTypeSupported('audio/mp4') ? 'audio/mp4' : 'audio/webm';
      const recorder = new MediaRecorder(stream, { mimeType });
      const chunks = [];
      recorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };
      recorder.onstart = () => { this.isRecording = true; this.searchResult = ''; this.searchQuery = '🎤 正在聆听...'; if (window.__VOICE_DEBUG__) console.log('[Voice] MediaRecorder started'); };
      recorder.onstop = async () => {
        if (window.__VOICE_DEBUG__) console.log('[Voice] stopped, chunks:', chunks.length);
        this.isRecording = false; this.searchQuery = '';
        stream.getTracks().forEach(t => t.stop());
        if (chunks.length === 0) { this.searchResult = '⚠️ 未录制到音频，请重试'; return; }
        const blob = new Blob(chunks, { type: mimeType });
        if (window.__VOICE_DEBUG__) console.log('[Voice] size:', (blob.size / 1024).toFixed(1), 'KB');
        this.searching = true; this.searchResult = '🎧 AI 正在聆听...';
        try {
          const form = new FormData();
          form.append('file', blob, 'recording.' + (mimeType.includes('mp4') ? 'mp4' : 'webm'));
          const speechAPI = axios.create({ baseURL: API_BASE.replace('/inspection', '/speech') });
          const r = await speechAPI.post('/transcribe', form);
          const text = r.data?.text || r.data?.transcript || '';
          if (window.__VOICE_DEBUG__) console.log('[Voice] result:', text);
          if (text.trim()) { this.searchQuery = text.trim(); this.doSearch(); }
          else { this.searchResult = '⚠️ 未识别到语音内容，请重试或使用文字输入'; this.searching = false; }
        } catch (e) { console.error('[Voice] 上传失败:', e); this.searchResult = '⚠️ 语音识别失败: ' + (e.response?.data?.detail || e.message || '网络错误'); this.searching = false; }
      };
      this._recorder = recorder; recorder.start();
      if (window.__VOICE_DEBUG__) console.log('[Voice] recording started...');
    } catch (e) {
      console.error('[Voice] getUserMedia 失败:', e); this.isRecording = false;
      if (e.name === 'NotAllowedError') {
        if (/^\d+\.\d+\.\d+\.\d+$/.test(location.hostname)) {
          this.searchResult = '麦克风权限被拒 - 检测到您正在使用IP地址访问，请在Chrome中打开 https://ai-bang.top/inspect/web/ 后使用语音功能。或直接打字搜索';
        } else if (/HarmonyOS|ArkWeb|HuaweiBrowser/.test(navigator.userAgent)) {
          this.searchResult = '鸿蒙自带浏览器限制麦克风访问 - 请安装Chrome浏览器打开 ai-bang.top/inspect/web/ 后使用语音。或直接打字搜索';
        } else {
          this.searchResult = '麦克风权限未开启 - 请点击地址栏左侧锁图标，将麦克风设为允许后重试。也可以直接打字搜索';
        }
      } else if (e.name === 'NotFoundError') { this.searchResult = '未找到麦克风设备，请使用文字输入检索'; }
      else { this.searchResult = '录音失败: ' + (e.message || '未知错误') + ' - 请使用文字输入检索'; }
    }
  },
  stopVoice() {
    if (this._recorder && this._recorder.state === 'recording') this._recorder.stop();
    if (this._mediaStream) this._mediaStream.getTracks().forEach(t => t.stop());
    this.isRecording = false;
  },

  // ═══ 语音判决（Phase 2.1）═════
  async startVoiceJudge() {
    if (this.isVoiceJudging) { this.stopVoiceJudge(); return; }
    if (!this.voiceAvailable()) { this.voiceJudgeText = '⚠️ ' + (this.voiceUnavailableReason() || '录音功能不可用，请使用Chrome浏览器'); return; }
    this.voiceJudgeText = '🎤 正在启动麦克风...';
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      this._voiceJudgeStream = stream;
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : 'audio/webm';
      const recorder = new MediaRecorder(stream, { mimeType });
      const chunks = [];
      recorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };
      recorder.onstart = () => { this.isVoiceJudging = true; this.voiceJudgeText = '🎤 正在聆听...'; this.voiceTimer = '00:00'; this._voiceStart = Date.now(); this._voiceInterval = setInterval(() => { const s = Math.floor((Date.now() - this._voiceStart) / 1000); this.voiceTimer = String(Math.floor(s/60)).padStart(2,'0') + ':' + String(s%60).padStart(2,'0'); if (s >= 15) this.stopVoiceJudge(); }, 200); };
      recorder.onstop = async () => {
        this.isVoiceJudging = false; this.voiceJudgeText = ''; this.voiceTimer = ''; clearInterval(this._voiceInterval);
        stream.getTracks().forEach(t => t.stop());
        if (chunks.length === 0) { this.voiceJudgeText = '⚠️ 未录制到音频'; return; }
        const blob = new Blob(chunks, { type: mimeType });
        this.voiceJudgeText = '🎧 识别中...';
        try {
          const form = new FormData();
          form.append('file', blob, 'judge.' + (mimeType.includes('mp4') ? 'mp4' : 'webm'));
          const speechAPI = axios.create({ baseURL: API_BASE.replace('/inspection', '/speech') });
          const r = await speechAPI.post('/transcribe', form);
          const text = r.data?.text || r.data?.transcript || '';
          this.voiceJudgeText = text ? ('📝 ' + text) : '⚠️ 未识别到语音';
          if (text) this._parseVoiceJudgment(text);
        } catch (e) {
          this.voiceJudgeText = '⚠️ 识别失败: ' + (e.message || '网络错误');
        }
      };
      this._voiceJudgeRecorder = recorder; recorder.start();
    } catch (e) {
      this.isVoiceJudging = false;
      this.voiceJudgeText = '⚠️ 麦克风权限未开启，请在浏览器设置中允许访问麦克风';
      if (e.name !== 'NotAllowedError') { this.voiceJudgeText = '⚠️ 录音失败: ' + (e.message || ''); console.error('[VoiceJudge]', e); }
    }
  },
  stopVoiceJudge() {
    if (this._voiceJudgeRecorder && this._voiceJudgeRecorder.state === 'recording') this._voiceJudgeRecorder.stop();
    if (this._voiceJudgeStream) this._voiceJudgeStream.getTracks().forEach(t => t.stop());
    this.isVoiceJudging = false;
  },
  _parseVoiceJudgment(text) {
    // 关键词提取：判定 + 描述
    const t = text.trim();
    let result, note = '';
    if (/合格|没问题|正常|符合|通过|合规/.test(t) && !/不/.test(t)) {
      result = 'pass'; note = t;
    } else if (/不合格|有问题|不行|隐患|过期|损坏|缺失|堵塞|故障|失效/.test(t)) {
      result = 'fail';
      // 提取描述：去掉"不合格"等关键词后的文字
      note = t.replace(/不合格[，。,.\s]*/, '').replace(/有问题[，。,.\s]*/, '');
      if (!note.trim()) note = t;
    } else if (/跳过|不涉及|N\/?A/.test(t)) {
      result = 'na'; note = '不涉及';
    } else if (/拍照|拍个照/.test(t)) {
      this.voiceJudgeText = '📸 请拍照';
      setTimeout(() => { this.showPhoto = true; this.voiceJudgeText = ''; }, 500);
      return;
    } else {
      this.voiceJudgeText = '🤔 无法识别: "' + t + '" — 请说"合格"或"不合格+描述"';
      return;
    }
    this.voiceJudgeText = '';
    this.judge(result, note);
  },
};
