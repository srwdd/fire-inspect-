// 消防监督检查智能辅助系统 — 扩展模块
// 语音搜索 + 拍照报告（从 app.js 提取，降低主文件复杂度）
const APP_EXTRAS = {
  // ═══ 拍照 + 报告 ═══
  async uploadPhoto(e) {
    const file = e.target.files[0];
    if (!file) return;
    this.photoAnalyzing = true;
    try {
      const form = new FormData();
      form.append('file', file);
      form.append('item_index', this.currentIndex);
      const r = await API.post(`/${this.inspectionId}/photo`, form);
      this.photoResult = r.data.data?.analysis || { violation: null, reason: '分析完成', confidence: 0 };
      // 加载典型隐患对比参考
      if (this.currentItem) {
        this.photoCompareHazard = this.getTypicalHazard(this.currentItem.facility);
      }
    } catch (e) {
      this.photoResult = { violation: null, reason: '分析失败: ' + e.message, confidence: 0 };
      this.photoCompareHazard = null;
    }
    this.photoAnalyzing = false;
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
    reader.onload = (ev) => { this.recheckPhoto = ev.target.result; };
    reader.readAsDataURL(file);
  },
  async viewReport() {
    try {
      const r = await API.get(`/${this.inspectionId}/report`);
      this.report = r.data.data;
      this.page = 'report';
    } catch (e) { alert('获取报告失败: ' + e.message); }
  },
  newInspection() { this.page = 'home'; this.report = null; this.ownerRpt = null; },
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
    const q = this.searchQuery.trim();
    if (!q) return;
    this.searching = true; this.searchResult = '';
    try {
      const chatAPI = axios.create({ baseURL: API_BASE.replace('/inspection', '/agent') });
      const r = await chatAPI.post('/chat', { message: q, scene: 'general' });
      this.searchResult = r.data.reply || r.data.answer || '未获取到结果';
    } catch (e) { this.searchResult = '查询失败: ' + (e.response?.data?.detail || e.message); }
    this.searching = false;
  },
  voiceAvailable() {
    return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia) && typeof MediaRecorder !== 'undefined' && (location.protocol === 'https:' || location.hostname === 'localhost');
  },
  voiceUnavailableReason() {
    if (typeof MediaRecorder === 'undefined') {
      const ua = navigator.userAgent;
      if (/iPad|iPhone|iPod/.test(ua)) return 'iOS 请使用 Safari 浏览器（iOS 14.5+）';
      if (/MicroMessenger/.test(ua)) return '微信内置浏览器不支持录音，请点击右上角"在浏览器中打开"';
      return '您的浏览器不支持录音功能，请使用 Chrome/Safari 浏览器';
    }
    if (location.protocol !== 'https:' && location.hostname !== 'localhost') return '录音功能需要 HTTPS 安全连接';
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
        alert(/Android/.test(navigator.userAgent) ? '麦克风权限未开启\n\n请在 Chrome 地址栏右侧点击🔒图标 → 权限 → 麦克风 → 允许\n\n或: 手机设置 → 应用管理 → Chrome → 权限 → 麦克风 → 允许' : '麦克风权限未开启\n\n请允许浏览器访问麦克风后重试\n\n（iOS: 设置 → Safari → 麦克风）');
      } else if (e.name === 'NotFoundError') { alert('未找到麦克风设备'); }
      else { alert('无法访问麦克风: ' + (e.message || '未知错误')); }
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
    if (!this.voiceAvailable()) { alert(this.voiceUnavailableReason()); return; }
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
      if (e.name !== 'NotAllowedError') console.error('[VoiceJudge]', e);
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
