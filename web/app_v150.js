const { createApp } = Vue;
const API_BASE = window.location.pathname.includes('/inspect') ? '/inspect/api/v1/inspection' : '/api/v1/inspection';
const API = axios.create({ baseURL: API_BASE });

// ── 移动端固定操作栏 CSS ──
(function() {
  var style = document.createElement('style');
  style.id = 'sticky-action-bar-css';
  style.textContent = [
    '.sticky-action-bar {',
    '  position: fixed; bottom: 0; left: 0; right: 0;',
    '  background: #fff; border-top: 1px solid #e5e5e5;',
    '  box-shadow: 0 -2px 12px rgba(0,0,0,.08);',
    '  z-index: 999; padding: 8px 10px;',
    '  display: flex; gap: 6px; align-items: center;',
    '  justify-content: center; flex-wrap: wrap;',
    '  padding-bottom: max(8px, env(safe-area-inset-bottom));',
    '}',
    '.sticky-action-bar button {',
    '  padding: 10px 14px; border-radius: 8px;',
    '  font-size: 14px; font-weight: 700; border: 1px solid #d9d9d9;',
    '  background: #fff; cursor: pointer; white-space: nowrap;',
    '  min-width: 52px; transition: all .15s;',
    '}',
    '.sticky-action-bar button.btn-pass {',
    '  background: #16a34a; color: #fff; border-color: #16a34a;',
    '}',
    '.sticky-action-bar button.btn-pass.active {',
    '  background: #15803d; box-shadow: 0 0 0 3px rgba(22,163,74,.3);',
    '}',
    '.sticky-action-bar button.btn-fail {',
    '  background: #dc2626; color: #fff; border-color: #dc2626;',
    '}',
    '.sticky-action-bar button.btn-fail.active {',
    '  background: #b91c1c; box-shadow: 0 0 0 3px rgba(220,38,38,.3);',
    '}',
    '.sticky-action-bar button.btn-na {',
    '  background: #f5f5f5; color: #999;',
    '}',
    '.sticky-action-bar button.btn-na.active {',
    '  background: #e5e5e5;',
    '}',
    '.sticky-action-bar button.btn-nav {',
    '  background: #1a1a2e; color: #fff; border-color: #1a1a2e;',
    '  padding: 10px 20px;',
    '}',
    '.sticky-action-bar .nav-info {',
    '  font-size: 12px; color: #8899aa; text-align: center;',
    '  min-width: 80px;',
    '}',
    '.inspect-page .check-card {',
    '  margin-bottom: 80px !important;',
    '}',
    '.inspect-page .nav-arrows {',
    '  opacity: 0.4;',
    '}',
  ].join('\n');
  document.head.appendChild(style);
})();
API.interceptors.request.use(function(c){ var t=localStorage.getItem("fire_token"); if(t) c.headers.Authorization="Bearer "+t; return c; });
// Auto-attach JWT token
API.interceptors.request.use(function(config) {
  var token = localStorage.getItem('fire_token');
  if (token) config.headers.Authorization = 'Bearer ' + token;
  return config;
});

const SCENES = [
  { key: 'hotel', total_items: 63, daily_items: 70, name: '宾馆/酒店', icon: '🏨', preopen: true },
  { key: 'mall', total_items: 63, daily_items: 70, name: '商场/市场', icon: '🏬', preopen: true },
  { key: 'entertainment', total_items: 63, daily_items: 70, name: '公共娱乐场所', icon: '🎤', preopen: true },
  { key: 'school', total_items: 36, daily_items: 68, name: '学校/幼儿园', icon: '🏫', preopen: false },
  { key: 'hospital', total_items: 37, daily_items: 69, name: '医院', icon: '🏥', preopen: false },
  { key: 'elderly', total_items: 38, daily_items: 69, name: '养老机构', icon: '🧓', preopen: false },
  { key: 'restaurant', total_items: 63, daily_items: 67, name: '餐饮场所', icon: '🍽️', preopen: true },
  { key: 'highrise', total_items: 36, daily_items: 69, name: '高层建筑', icon: '🏢', preopen: false },
  { key: 'mixed_use', total_items: 71, name: '多业态混合', icon: '🏗️', preopen: false },
  { key: 'factory', total_items: 75, name: '厂房/仓库', icon: '🏭', preopen: false },
  { key: 'crowded', total_items: 76, name: '人员密集场所', icon: '👥', preopen: false },
  { key: 'nine_small', total_items: 59, name: '九小场所', icon: '🏪', preopen: false },
];

// 设施操作测试指南（现场测试用）
const OPERATION_GUIDES = {
  '消火栓系统': {
    question: '请现场测试室内消火栓的出水压力和启泵功能',
    steps: ['打开消火栓箱门（箱门开启角度≥160°）','检查箱内器材：水枪×1、水带×1（25m）、栓阀','展开水带，连接水枪和栓阀接口','逆时针旋转手轮全开栓阀','握紧水枪对准排水方向，观察充实水柱（一般≥10m，高层≥13m）','按下消火栓箱内启泵按钮','到消防控制室确认：控制器收到启泵反馈信号，水泵30秒内启动'],
    passCriteria: '水压充足、充实水柱达标、启泵按钮有效、控制室收到信号',
    video: '/inspect/api/v1/inspection/videos/%E6%B6%88%E7%81%AB%E6%A0%93%E7%B3%BB%E7%BB%9F-%E6%9F%A5%E9%AA%8C%E6%95%99%E5%AD%A6.mp4',
  },
  '火灾自动报警系统': {
    question: '请测试火灾自动报警系统的探测器报警和控制器响应功能',
    steps: ['在消防控制室查看控制器面板：确认无故障灯/屏蔽灯常亮','抽查2个感烟探测器：使用专用烟感测试器加烟','观察控制器：30秒内收到报警信号，显示正确地址编码和部位','按下1个手动报警按钮','观察控制器：3秒内收到信号，启动声光报警器和应急广播','检查控制器主备电切换：断开主电源，备电应自动投入'],
    passCriteria: '探测器30s内报警、地址正确、手报3s内响应、主备电切换正常',
    video: '/inspect/api/v1/inspection/videos/%E7%81%AB%E7%81%BE%E8%87%AA%E5%8A%A8%E6%8A%A5%E8%AD%A6%E7%B3%BB%E7%BB%9F-%E6%9F%A5%E9%AA%8C%E6%95%99%E5%AD%A6.mp4',
  },
  '自动喷水灭火系统': {
    question: '请测试自动喷水灭火系统末端试水装置',
    steps: ['找到系统最不利点的末端试水装置','打开末端试水阀','观察压力表读数：应≥0.05MPa','观察水流指示器：应动作并反馈信号至控制室','等待5分钟内压力开关动作并直接启动喷淋泵','到控制室确认：收到水流指示器、压力开关、喷淋泵启动信号','关闭试水阀，系统恢复'],
    passCriteria: '压力≥0.05MPa、水流指示器动作、压力开关启泵、控制室信号齐全',
    video: '/inspect/api/v1/inspection/videos/%E8%87%AA%E5%8A%A8%E5%96%B7%E6%B0%B4%E7%81%AD%E7%81%AB%E7%B3%BB%E7%BB%9F-%E6%9F%A5%E9%AA%8C%E6%95%99%E5%AD%A6.mp4',
  },
  '防排烟系统': {
    question: '请测试防排烟风机的启动和联动功能',
    steps: ['在消防控制室远程手动启动排烟风机→确认风机运转、收到反馈','现场手动启动送风机→确认运转方向正确','触发2个火灾探测器（联动测试）：风机自动启动','观察送风口/排烟口自动开启','排烟风机入口处的排烟防火阀：手动测试关闭→排烟风机应连锁停止','确认消防控制室显示所有风机、风口、防火阀状态'],
    passCriteria: '三种启动方式均正常、风口正确开启、防火阀连锁关闭有效',
    video: '/inspect/api/v1/inspection/videos/%E9%98%B2%E6%8E%92%E7%83%9F%E7%B3%BB%E7%BB%9F-%E6%9F%A5%E9%AA%8C%E6%95%99%E5%AD%A6.mp4',
  },
  '防火门': {
    question: '请检查防火门的闭门器、顺序器和联动关闭功能',
    steps: ['常闭防火门：手动开启后释放→应自动关闭严密','双扇防火门：开启后释放→顺序器控制关闭顺序正确','检查闭门器：无漏油、弹簧有效','测量门扇与门框缝隙：≥2mm不合格','常开防火门：触发火灾报警→应联动自动关闭','消防控制室：确认收到防火门关闭反馈信号'],
    passCriteria: '自闭严密、顺序正确、闭门器完好、常开门联动关闭有效',
    video: '/inspect/api/v1/inspection/videos/%E5%BB%BA%E7%AD%91%E9%98%B2%E7%81%AB-%E6%9F%A5%E9%AA%8C%E6%95%99%E5%AD%A6.mp4',
  },
  '防火卷帘': {
    question: '请测试防火卷帘的手动和联动降落功能',
    steps: ['外观检查：帘板无锈蚀、导轨无卡阻、下方0.3m黄色警示线内无物品','操作两侧手动按钮：上升↓下降↓停止 均正常','操作手动速放链条：卷帘应能靠自重下降','疏散通道处：触发1个感烟探测器→卷帘降至距地1.8m','触发感温探测器→卷帘降到底','非疏散通道处：触发2个探测器→一步降到底','消防控制室：确认收到卷帘动作反馈信号'],
    passCriteria: '手动/联动升降正常、一步降/两步降正确、控制室反馈到位',
    video: '/inspect/api/v1/inspection/videos/%E5%BB%BA%E7%AD%91%E9%98%B2%E7%81%AB-%E6%9F%A5%E9%AA%8C%E6%95%99%E5%AD%A6.mp4',
  },
  '灭火器配置': {
    question: '请检查灭火器的配置、压力和有效期',
    steps: ['抽查3个配置点的灭火器','查看压力表：指针必须在绿区','查看生产日期和维修标签：在有效期内（干粉5年、CO₂ 3年）','检查筒体：无锈蚀、变形','检查喷射软管和保险销：完好','核对灭火器类型是否与场所火灾类别匹配','核对配置数量是否符合GB 50140要求'],
    passCriteria: '压力绿区、有效期内、筒体完好、类型匹配、数量足够',
    video: '/inspect/api/v1/inspection/videos/%E7%81%AD%E7%81%AB%E5%99%A8%E9%85%8D%E7%BD%AE.mp4',
  },
  '消防应急照明和疏散指示标志': {
    question: '请测试应急照明灯的切换和持续时间',
    steps: ['抽查任一疏散路线上的3处应急照明灯','切断主电源→灯具应在5s内自动切换至应急状态','使用照度计测量地面最低水平照度：疏散走道≥1.0lx、人员密集场所≥3.0lx','记录应急照明持续时间→应≥90分钟','核查疏散指示标志的方向→应指向最近安全出口','确认标志安装高度和间距符合要求'],
    passCriteria: '5s内切换、照度达标、持续时间≥90分钟、方向正确',
    video: '/inspect/api/v1/inspection/videos/%E6%B6%88%E9%98%B2%E5%BA%94%E6%80%A5%E7%85%A7%E6%98%8E.mp4',
  },
  '电气线路安全': {
    question: '请检查电气线路的敷设和保护措施',
    steps: ['查看吊顶内、墙体内的电气线路敷设方式','有可燃物的吊顶/墙体：线路应穿金属导管或封闭金属槽盒保护','查看电热设备：靠近可燃物时应有隔热散热措施','检查是否设有电气火灾监控系统（按规范需要时）','检查配电箱：箱门完好、无裸露导线、接地线完好'],
    passCriteria: '穿管保护到位、隔热措施完善、配电箱完好、接地可靠',
    video: '/inspect/api/v1/inspection/videos/%E6%B6%88%E9%98%B2%E7%94%B5%E6%B0%94-%E6%9F%A5%E9%AA%8C%E6%95%99%E5%AD%A6.mp4',
  },
  '消防电梯': {
    question: '请测试消防电梯的迫降和运行功能',
    steps: ['现场检查消防电梯前室面积和防火分隔','触发火灾报警→消防电梯应自动迫降至首层','检查消防电梯轿厢内：应设消防电话分机','手动操作消防电梯：从首层到顶层运行时间≤60s','测试消防电梯的消防员操作功能','消防控制室：确认显示消防电梯运行状态'],
    passCriteria: '自动迫降有效、运行时间≤60s、消防电话可用、设防水措施',
    video: '/inspect/api/v1/inspection/videos/%E6%B6%88%E9%98%B2%E7%94%B5%E6%A2%AF-%E6%9F%A5%E9%AA%8C%E6%95%99%E5%AD%A6.mp4',
  },
  '消防控制室值班': {
    question: '请测试消防控制室值班人员的设备操作能力',
    steps: ['确认值班人员持证上岗、每班≥2人','要求值班员操作火灾报警控制器：消音→查看信息→复位','要求值班员使用消防电话总机呼叫水泵房分机','要求值班员启动应急广播进行全楼广播','查看值班记录：完整、至少保存1年','确认控制器处于自动状态（非手动）'],
    passCriteria: '持证上岗、双人值班、操作熟练、记录完整、控制器自动状态',
    video: '/inspect/api/v1/inspection/videos/%E6%B6%88%E9%98%B2%E6%8E%A7%E5%88%B6%E5%AE%A4%E5%80%BC%E7%8F%AD.mp4',
  },
  '消防水泵接合器': {
    question: '请检查消防水泵接合器的状态和标识',
    steps: ['现场查看水泵接合器外观完整性','检查是否被埋压、圈占、遮挡','查看永久性标志铭牌：标明供水系统类型和供水范围','确认距建筑外墙边缘≥5m','检查接口密封盖完好'],
    passCriteria: '无埋压遮挡、标识清晰、距外墙≥5m、接口完好',
    video: '/inspect/api/v1/inspection/videos/%E6%B6%88%E7%81%AB%E6%A0%93%E7%B3%BB%E7%BB%9F-%E6%9F%A5%E9%AA%8C%E6%95%99%E5%AD%A6.mp4',
  },
  '消防供电': {
    question: '请测试消防供电和备用电源切换功能',
    steps: ['确认消防用电设备采用专用供电回路','在消防控制室断开主电源→备用电源应自动投入','记录切换时间：≤15s','检查柴油发电机房（如有）：储油量≤1m³、防火分隔完好','测试发电机自启动：市电中断后15s内启动、30s内供电','检查配电柜：双电源转换开关（ATS）正常'],
    passCriteria: '专用回路、备电自动投入、切换≤15s、发电机正常启动',
    video: '/inspect/api/v1/inspection/videos/%E6%B6%88%E9%98%B2%E7%94%B5%E6%B0%94-%E6%9F%A5%E9%AA%8C%E6%95%99%E5%AD%A6.mp4',
  },
	  
	  '消防电话': { question: '请测试消防电话系统', steps: ['核查关键部位均有消防电话分机','控制室总机逐一呼叫各分机','通话清晰无杂音','线路采用独立回路'], passCriteria: '分机到位、通话清晰、线路独立' },
	  '消防广播': { question: '请测试消防应急广播', steps: ['扬声器覆盖: 走道/大厅均有、间距≤25m','强制切换: 音量最小→火警→自动最大音量播放','分区广播: 按楼层/防火分区选择','全楼广播: 可同时播放疏散指令'], passCriteria: '覆盖到位、强制切换正常' },
	  '疏散': { question: '请检查疏散设施', steps: ['走道畅通、宽度≥1.1m','安全出口数量≥2个、向外开启','疏散指示间距≤20m','地面照度走道≥1.0lx/密集场所≥3.0lx'], passCriteria: '畅通、宽度达标、指示清晰、照度合格' },
	  '安全出口': { question: '请检查安全出口', steps: ['数量: 公共建筑≥2个','开启方向: 向疏散方向','门外1.4m无台阶','无锁闭/堵塞/遮挡','上方安全出口标志灯完好'], passCriteria: '数量足够、畅通无阻、标志完好' },
	  '消防水泵': { question: '请检查消防水泵接合器', steps: ['外观完好、无埋压/圈占/遮挡','标志铭牌清晰','距外墙≥5m','接口密封盖完好'], passCriteria: '无埋压遮挡、标识清晰' },
	  '防烟分区': { question: '请检查防烟分区', steps: ['每个分区≤500m²、不跨越防火分区','挡烟垂壁完好有效','底部距地面≥2.0m'], passCriteria: '分区合理、挡烟垂壁完好' },
	  
  '气体灭火系统': {
    question: '请检查气体灭火系统的储瓶和防护区',
    steps: ['检查储瓶间压力表在绿区（CO2称重≤5%）','电磁阀与瓶头阀连接牢固','启动管路无堵塞','抽查1个防护区门窗能自动关闭','泄压口位置正确、放气指示灯完好'],
    passCriteria: '储瓶压力正常、防护区密闭、放气指示灯完好',
    video: '/inspect/api/v1/inspection/videos/%E6%B0%94%E4%BD%93%E7%81%AD%E7%81%AB%E7%B3%BB%E7%BB%9F-%E6%9F%A5%E9%AA%8C%E6%95%99%E5%AD%A6.mp4',
  },
  '泡沫灭火系统': {
    question: '请检查泡沫灭火系统的泡沫液和比例混合器',
    steps: ['检查泡沫液有效期内（≤3年）','储罐无锈蚀泄漏','比例混合器未堵塞','泡沫产生器过滤网清洁、吸气口通畅'],
    passCriteria: '泡沫液有效、储罐完好、混合比达标',
    video: '/inspect/api/v1/inspection/videos/%E6%B3%A1%E6%B2%AB%E7%81%AD%E7%81%AB%E7%B3%BB%E7%BB%9F.mp4',
  },
	  '疏散': { question: '请检查疏散设施', steps: ['走道畅通、宽度≥1.1m','安全出口数量≥2个、向外开启','疏散指示间距≤20m','地面照度走道≥1.0lx/密集场所≥3.0lx'], passCriteria: '畅通、宽度达标、指示清晰、照度合格' },
	  '安全出口': { question: '请检查安全出口', steps: ['数量: 公共建筑≥2个','开启方向: 向疏散方向','门外1.4m无台阶','无锁闭/堵塞/遮挡','上方安全出口标志灯完好'], passCriteria: '数量足够、畅通无阻、标志完好' },
	  '消防水泵': { question: '请检查消防水泵接合器', steps: ['外观完好、无埋压/圈占/遮挡','标志铭牌清晰','距外墙≥5m','接口密封盖完好'], passCriteria: '无埋压遮挡、标识清晰' },
	  '防烟分区': { question: '请检查防烟分区', steps: ['每个分区≤500m²、不跨越防火分区','挡烟垂壁完好有效','底部距地面≥2.0m'], passCriteria: '分区合理、挡烟垂壁完好' },

	};
// 典型隐患参考（覆盖所有检查项）
const TYPICAL_HAZARDS = {
  '灭火器': { desc: '压力表红区(失压)、瓶体锈蚀、喷管老化断裂、保险销丢失、超期未检(干粉5年/CO₂ 3年)、被杂物遮挡取用不便、配置数量不足' },
  '消火栓': { desc: '水带缺失或老化、水枪锈蚀、栓阀漏水或卡死、水压不足(充实水柱<10m)、启泵按钮失效、箱门变形(开启<160°)、箱前1.5m内有障碍物、最不利点静压不达标' },
  '火灾自动报警': { desc: '探测器被污染/防尘罩未摘/被遮挡、控制器有故障灯或屏蔽灯常亮、主备电切换失败、手动报警按钮损坏或不通、系统接地电阻>4Ω、声光报警器不响或不亮' },
  '自动喷水': { desc: '喷头被涂料覆盖或被吊顶遮挡、热敏玻璃球变色或破损、末端试水压力<0.05MPa、报警阀组阀门关闭、水流指示器不动作、水力警铃不响、压力开关不能启泵' },
  '防排烟': { desc: '排烟口被封堵或卡死、风机无法启动(手动/远程/联动)、送风口开启角度不够、排烟防火阀锈死不能关闭、自然排烟窗被固定或遮挡、挡烟垂壁缺失或损坏' },
  '疏散通道': { desc: '堆放杂物(货物/家具/垃圾)、宽度不足1.1m、应急照明损坏、疏散指示标志缺失或方向错误、地面有高差无坡道' },
  '安全出口': { desc: '锁闭或堵塞、门向错误方向开启、数量不足2个(公共娱乐场所)、门外1.4m内有台阶、上方无安全出口标志灯' },
  '防火门': { desc: '常闭防火门未关闭或被物品卡住、闭门器漏油或弹簧失效、双扇门顺序器损坏(关闭顺序错误)、门框未灌浆(空心)、门扇与门框缝隙>2mm、常开防火门联动关闭失效' },
  '电气线路': { desc: '未穿管保护(直接敷设在可燃物上)、私拉乱接电线、配电箱无漏电保护、电线接头松动发热、电动车在疏散通道/楼梯间/安全出口停放或充电' },
  '消防控制室': { desc: '仅有1人值班(应≥2人)、值班人员无消防设施操作员证、火灾报警控制器处于手动状态、值班记录不完整或未保存1年、堆放杂物、无外线电话' },
  '防火卷帘': { desc: '帘板锈蚀变形、导轨卡阻不能顺畅升降、下方黄色警示线内堆放物品、手动速放链条损坏或缺失、联动降落失效(一步降或两步降不正确)' },
  '应急照明': { desc: '灯具外观损坏、切断主电源后不能自动切换至应急状态(5s内)、地面照度不达标(走道≥1lx/密集场所≥3lx/楼梯≥5lx)、持续供电<90分钟' },
  '消防电梯': { desc: '前室面积不足或防火分隔损坏、消防电梯不能迫降至首层、轿厢内消防电话分机缺失或不通、电梯井底无排水设施、运行时间>60s(首层到顶层)' },
  '消防水泵': { desc: '水泵无法启动(手动/远程/联动)、运行时有异常振动或噪音、泵体或管道漏水、控制柜故障灯亮、无定期启动测试记录' },
  '消防水池': { desc: '水位过低(低于正常水位线)、进水阀关闭或故障、液位显示装置损坏、水质浑浊有杂物、溢流管和泄水管无防虫网' },
  '消防水箱': { desc: '出水管阀门关闭、水位不足、稳压泵频繁启停或失效、冬季无防冻措施结冰、通气管无防虫网' },
  '水泵接合器': { desc: '被埋压/圈占/遮挡、接口密封盖丢失、未标明供水系统和供水范围、距建筑外墙<5m、止回阀损坏漏水' },
  '发电机': { desc: '发电机不能自启动(市电中断后15s内)、ATS转换开关故障、储油间超量(>1m³)、油箱油位过低、蓄电池电压不足、排烟管隔热层破损' },
  '消防电话': { desc: '分机与总机通话不清晰或有杂音、消防水泵房/发电机房/变配电室等关键部位未设分机、线路与其他系统共用' },
  '消防广播': { desc: '扬声器间距>25m或功率<3W、火灾时不能强制切入应急广播状态、音量调节器未被旁路、分区广播功能故障、备用电源<30分钟' },
  '气体灭火': { desc: '储瓶压力表不在绿区(CO₂系统称重失重>5%)、电磁阀与瓶头阀连接松动、启动管路堵塞、防护区门窗不能自动关闭、泄压口位置不当、放气指示灯不亮' },
  '泡沫灭火': { desc: '泡沫液超过有效期(通常≤3年)、储罐锈蚀或泄漏、比例混合器堵塞(混合比不达标)、泡沫产生器过滤网堵塞、吸气口不通畅' },
  '消防供电': { desc: '消防设备未采用专用供电回路、备用电源切换时间>15s、柴油发电机储油量超标或不达标、配电柜双电源转换开关(ATS)失效' },
  '消防安全责任制': { desc: '制度文件缺失或不完整、未签订责任书、未明确各级各岗位责任人、抽查员工不知晓本岗位消防职责' },
  '消防安全责任人': { desc: '责任人未由法定代表人/主要负责人/实际控制人担任、对消防法律法规不熟悉、不掌握本单位消防安全状况' },
  '消防安全教育培训': { desc: '新员工未进行岗前消防培训、全员未每半年培训一次、抽问员工不掌握一懂三会(懂火灾危险、会报警、会灭火、会逃生)' },
  '防火巡查检查记录': { desc: '巡查记录缺失或不完整、营业期间未每2小时巡查(公众聚集场所)、巡查发现的问题未闭环整改、记录无巡查人签字' },
  '消防设施维护保养': { desc: '无定期维保记录、未每年至少一次全面检测、维保检测机构无资质、发现的问题未及时修复、消防设施因维修停用未公告' },
  '灭火和应急疏散预案': { desc: '预案内容缺项(缺组织机构/处置程序/疏散措施等)、未每半年组织一次演练、演练走过场无照片或记录、员工不熟悉本岗位应急任务' },
  '用火用电': { desc: '动火作业未审批、无专人监护、未清理可燃物、电气线路私拉乱接、配电箱周围堆放可燃物' },
  '微型消防站': { desc: '未按标准建站(人员≥6人/器材配备不足)、队员不熟悉消防设施位置和操作、未定期组织训练和演练、装备过期或损坏未更换' },
  '燃气': { desc: '燃气管道锈蚀或漏气、未设可燃气体探测报警装置、手动和自动切断装置失效、瓶组间设置不符合要求(防火分隔不足)' },
  '厨房烟道': { desc: '油烟管道长期未清洗(积油≥2mm)、未每季度至少清洗一次、清洗记录不全、烟道防火阀未定期测试' },
  '电气线路安全': { desc: '线路未穿金属管或阻燃塑料管、导线接头松动或发热、绝缘层老化破损、配电箱内线路混乱无标识、漏电保护开关失效' },
  '消防档案': { desc: '档案不全(缺消防设施清单/图纸/维保记录)、未及时更新、档案保管不善(损坏或丢失)' },
  '消防产品': { desc: '产品无合格证或CCC认证标志、灭火器/应急灯等超期使用、产品铭牌信息不清、外观损坏影响使用功能' },
  '重大火灾隐患': { desc: '判定条件: 消防设施不能正常运行/安全出口数量不足/防火分区被改变且无法当场改正/消防控制室无人值班或无证上岗/违规使用易燃可燃材料装修' },
};

function getTypicalHazard(facility) {
  for (const [k, v] of Object.entries(TYPICAL_HAZARDS)) {
    if (facility && facility.includes(k)) return v;
  }
  return null;
}

// 关键词→操作指南映射（比字符串匹配更鲁棒）
const GUIDE_KEYWORDS = {
  '消火栓系统': ['消火栓','启泵','消防给水','水带','栓阀','消防水泵','消防水池','消防水箱'],
  '火灾自动报警系统': ['火灾自动报警','火灾报警','报警控制器','探测器','声光','手动火灾报警','手动报警','消防电话','消防广播','联动控制','火灾探测器','火灾警报'],
  '自动喷水灭火系统': ['自动喷水','喷淋','喷头','末端试水','水流指示器','报警阀','洒水喷头'],
  '防排烟系统': ['排烟','防烟','送风','防火阀','排烟窗','挡烟垂壁','自然排烟','风机启动'],
  '防火门': ['防火门','闭门器','顺序器','耐火等级'],
  '防火卷帘': ['防火卷帘'],
  '灭火器配置': ['灭火器'],
  '消防应急照明和疏散指示标志': ['应急照明','疏散指示','应急灯','疏散通道','安全出口','疏散楼梯'],
  '电气线路安全': ['电气线路','配电','电线','电缆井','管道井'],
  '消防电梯': ['消防电梯'],
  '消防控制室值班': ['消防控制室','值班','图形显示'],
  '消防水泵接合器': ['水泵接合器'],
  '消防供电': ['消防供电','发电','ATS','备用电源'],
  '气体灭火系统': ['气体灭火','储瓶','气瓶','防护区'],
  '泡沫灭火系统': ['泡沫灭火','泡沫液','比例混合'],
};

function getOperationGuide(facility) {
  if (!facility) return null;
  // 精确匹配优先
  for (const [k, v] of Object.entries(OPERATION_GUIDES)) {
    if (facility.includes(k)) return v;
  }
  // 关键词匹配
  for (const [k, keywords] of Object.entries(GUIDE_KEYWORDS)) {
    for (const kw of keywords) {
      if (facility.includes(kw)) return OPERATION_GUIDES[k];
    }
  }
  return null;
}

createApp({
  data() {
    return {
      page: ((sessionStorage.getItem('fire_token') || localStorage.getItem('fire_token')) && (sessionStorage.getItem('fire_user') || localStorage.getItem('fire_user'))) ? 'home' : 'login',
      theme: localStorage.getItem('fire_theme') || 'dark',
      currentUser: JSON.parse(sessionStorage.getItem('fire_user') || localStorage.getItem('fire_user') || 'null'),
      token: sessionStorage.getItem('fire_token') || localStorage.getItem('fire_token') || '',
      fuzzyAPI: axios.create({ baseURL: API_BASE.replace('/inspection', '/speech') }),
      currentUser: JSON.parse(sessionStorage.getItem('fire_user') || localStorage.getItem('fire_user') || 'null'),
      loginUsername: '',
      loginPassword: '',
      loginError: '',
      token: sessionStorage.getItem('fire_token') || localStorage.getItem('fire_token') || '',
      currentUser: JSON.parse(sessionStorage.getItem('fire_user') || localStorage.getItem('fire_user') || 'null'),
      loginUsername: '',
      loginPassword: '',
      loginError: '',
      inspectType: 'preopen',  // preopen | daily
      mode: 'first',
      scenes: SCENES,
      searchVenue: '',
      searched: false,
      historyList: [],
      // 检查状态
      inspectionId: (new URLSearchParams(window.location.search)).get('report') || '',
      currentIndex: 0,
      totalItems: 0,
      currentItem: null,
      currentSectionName: '',
      currentStepName: '',
      inspected: false,
      failCount: 0,
      judgedCount: 0,
      judgments: {},    // {itemIndex: {result, note, ...}}
      // 拍照
      showPhoto: false,
      photoAnalyzing: false,
      photoResult: null,
      // 报告
      report: null,
      // 搜索
      searchQuery: '',
      searching: false,
      searchResult: '',
      isRecording: false,
      isVoiceJudging: false,
      voiceJudgeText: "",
      recognition: null,
      // 规模参数 + 子类型
      showScaleInput: false,
      allOrgs: [],
      allUsers: [],
      newUser: { username: '', password: '', display_name: '', role: 'lead', org_id: 0 },
      adminMsg: '',
      orgUsers: [],
      selectedLeadId: 0,
      selectedAssistId: 0,
      showSubTypePicker: false,
      scaleForm: { area: '', staff: '', floors: '', buildings: '1', venueName: '', venueAddress: '' },
      selectedSubType: '',
      pendingScene: null,
      samplingInfo: null,
      selectedBrand: '',
      showQaAnswer: false,
      showOpGuide: false,
      showDetail: false,
      recheckPhoto: null, recheckPreviewData: null,
      loading: false, loadingText: '', toast: null,
      // 计算器 + 智能诊断
      showCalc: false,
      calcType: '',
      calcResult: null,
      calcInput: {},
      showDiagnosis: false,
      showIssueList: false,
      diagnosis: null,
      ownerRpt: null,
      showJumpMenu: false,
      sectionIndex: {},
      lastReportId: localStorage.getItem('fire_last_inspection_id') || '',
      inspectionHistory: JSON.parse(localStorage.getItem('fire_inspection_history') || '[]'),
      activeInspections: [],
      pendingRechecks: [],
      showOwnerCard: true,
      ownerSubmissions: [],
      ownerNewLink: {venue_type:'hotel',venue_name:'',venue_address:''},
      ownerNewCode: '',
      dashboard: null, // 数据看板
      jumpKeyword: '',
      jumpFiltered: null,
      updateReady: false,
      // WebSocket 协办
      ws: null,
      wsConnected: false,
      wsReconnectTimer: null,
      wsReconnectDelay: 1000,
      hasAssistant: false,       // 选了协办才启用 WS
      pendingConfirm: false,     // 等待协办确认中
      nineSmallSubTypes: [
        '小商店/小超市', '小餐饮/小吃店', '小旅馆/民宿', '小娱乐/网吧',
        '小诊所/卫生室', '小培训机构/托育', '小加工/小仓储', '其他小场所'
      ],
      // 视频弹窗
      showVideoModal: false,
      currentVideoUrl: '',
      currentVideoTitle: '',
      // 开业前检查分组映射 (移动自 methods，Vue 3 methods 只能放函数)
      preopenOrderMap: [
        [490,509,1,0,0],[510,519,1,0,0],[520,529,3,0,0],
        [530,539,2,1,1],[540,549,2,1,2],[550,559,2,1,3],
        [560,564,2,1,4],[565,569,2,1,5],
        [570,579,2,2,10],[580,589,2,2,8],[590,599,2,2,9],
        [600,609,2,2,6],[610,619,2,2,7],[620,629,2,2,17],
        [630,639,2,2,11],[640,649,2,1,3],[650,659,2,1,3],
        [660,669,2,2,12],[670,679,2,2,14],[680,689,2,2,13],
        [690,699,2,2,13],[700,709,2,2,15],[710,719,2,2,16],
        [720,799,2,2,17],[800,899,4,0,0],
      ],
    };
  },

  computed: {
    issueList() {
      var list = [];
      for (var i = 0; i < this.totalItems; i++) {
        var j = this.judgments[i];
        if (j && j.result === 'fail') {
          var item = (this._itemsCache && this._itemsCache[i]) || {};
          list.push({ index: i, facility: item.facility || ('第'+(i+1)+'项'), note: j.note || '' });
        }
      }
      return list;
    },
    progressPct() {
      if (!this.totalItems) return 0;
      return Math.min(100, Math.round((this.judgedCount / this.totalItems) * 100));
    },
  },

  mounted() {
    var self = this;
    this.$nextTick(function() {
      if (self.page === 'home') { self.loadActiveInspections(); self.loadOwnerSubmissions(); }
    });
  },
  watch: {
    page(val) { if (val === 'home') { var hist = JSON.parse(localStorage.getItem('fire_inspection_history') || '[]'); if (hist.length) { var cleaned = hist.filter(function(h) { return h.total > 0 && !(h.total === 0 && h.score === 100); }); if (cleaned.length !== hist.length) localStorage.setItem('fire_inspection_history', JSON.stringify(cleaned)); } this.loadActiveInspections(); this.loadOwnerSubmissions(); } }
  },
  created() {
    if ('serviceWorker' in navigator) {
      var self = this;
      navigator.serviceWorker.addEventListener('message', function(e) {
        if (e.data && e.data.type === 'UPDATE_AVAILABLE') self.updateReady = true;
      });
    }
  },
  methods: {
    toggleTheme() {
      this.theme = this.theme === 'light' ? 'dark' : 'light';
      this.inspectionHistory = JSON.parse(localStorage.getItem('fire_inspection_history') || '[]');
    document.body.classList.toggle('light-mode', this.theme === 'light');
      localStorage.setItem('fire_theme', this.theme);
    },
    async doLogin() {
      this.loginError = '';
      try {
        var authAPI = axios.create({ baseURL: API_BASE.replace('/inspection', '/auth') });
        var r = await authAPI.post('/login', { username: this.loginUsername, password: this.loginPassword });
        var d = r.data.data;
        this.token = d.token;
        this.currentUser = d.user;
        localStorage.setItem('fire_token', d.token);
        localStorage.setItem('fire_user', JSON.stringify(d.user));
        sessionStorage.setItem('fire_token', d.token);
        sessionStorage.setItem('fire_user', JSON.stringify(d.user));
        this.loginPassword = '';
        this._removeStickyActionBar();
      this.page = 'home';
        // 清理过期的本地检查记录 (0项/100分的脏数据)
      var hist = JSON.parse(localStorage.getItem('fire_inspection_history') || '[]');
      if (hist.length) {
        var cleaned = hist.filter(function(h) { return h.total > 0 && !(h.total === 0 && h.score === 100); });
        if (cleaned.length !== hist.length) localStorage.setItem('fire_inspection_history', JSON.stringify(cleaned));
      }
      this.loadActiveInspections(); var self = this; setTimeout(function() { self.loadActiveInspections(); }, 500);
      } catch (e) {
        this.loginError = e.response?.data?.detail || '登录失败，请检查用户名密码';
      }
    },
    _errMsg(e, defaultMsg) {
      var d = (e && e.response && e.response.data) || {};
      if (typeof d.detail === 'string') return d.detail;
      if (Array.isArray(d.detail) && d.detail.length > 0) {
        return d.detail.map(function(x) { return x.msg || ''; }).filter(Boolean).join('; ');
      }
      if (typeof d.detail === 'object' && d.detail !== null) {
        try { return JSON.stringify(d.detail); } catch(_) {}
      }
      if (e && e.message && typeof e.message === 'string') return e.message;
      return defaultMsg || '未知错误';
    },
    async createUser() {
      var u = this.newUser;
      if (!u.username || !u.password || !u.display_name) { this.adminMsg = '请填写完整信息'; return; }
      try {
        var authAPI = axios.create({ baseURL: API_BASE.replace('/inspection', '/auth') });
        await authAPI.post('/users', u);
        this.adminMsg = '创建成功: ' + u.display_name;
        this.newUser = { username: '', password: '', display_name: '', role: 'lead', org_id: 0 };
        var r = await authAPI.get('/users'); this.allUsers = r.data.data || [];
      } catch(e) { this.adminMsg = '创建失败: ' + (e.response?.data?.detail || e.message); }
    },
    async doLogin() {
      this.loginError = '';
      try {
        var authAPI = axios.create({ baseURL: API_BASE.replace('/inspection', '/auth') });
        var r = await authAPI.post('/login', { username: this.loginUsername, password: this.loginPassword });
        var d = r.data.data;
        this.token = d.token;
        this.currentUser = d.user;
        localStorage.setItem('fire_token', d.token);
        localStorage.setItem('fire_user', JSON.stringify(d.user));
        sessionStorage.setItem('fire_token', d.token);
        sessionStorage.setItem('fire_user', JSON.stringify(d.user));
        this.loginPassword = '';
        this._removeStickyActionBar();
      this.page = 'home';
        // 清理过期的本地检查记录 (0项/100分的脏数据)
      var hist = JSON.parse(localStorage.getItem('fire_inspection_history') || '[]');
      if (hist.length) {
        var cleaned = hist.filter(function(h) { return h.total > 0 && !(h.total === 0 && h.score === 100); });
        if (cleaned.length !== hist.length) localStorage.setItem('fire_inspection_history', JSON.stringify(cleaned));
      }
      this.loadActiveInspections(); var self = this; setTimeout(function() { self.loadActiveInspections(); }, 500);
      } catch (e) {
        this.loginError = this._errMsg(e, '登录失败');
      }
    },
    async createUser() {
      var u = this.newUser;
      if (!u.username || !u.password || !u.display_name) { this.adminMsg = '请填写完整信息'; return; }
      try {
        var authAPI = axios.create({ baseURL: API_BASE.replace('/inspection', '/auth') });
        await authAPI.post('/users', u);
        this.adminMsg = '创建成功: ' + u.display_name;
        this.newUser = { username: '', password: '', display_name: '', role: 'lead', org_id: 0 };
        var r = await authAPI.get('/users'); this.allUsers = r.data.data || [];
      } catch(e) { this.adminMsg = '创建失败: ' + (e.response?.data?.detail || e.message); }
    },
    // 回到首页时加载活跃检查
    goHome() {
      this._removeStickyActionBar();
      this.page = 'home'; var self = this; setTimeout(function() { self.loadActiveInspections(); }, 500);
      // 清理过期的本地检查记录 (0项/100分的脏数据)
      var hist = JSON.parse(localStorage.getItem('fire_inspection_history') || '[]');
      if (hist.length) {
        var cleaned = hist.filter(function(h) { return h.total > 0 && !(h.total === 0 && h.score === 100); });
        if (cleaned.length !== hist.length) localStorage.setItem('fire_inspection_history', JSON.stringify(cleaned));
      }
      this.loadActiveInspections();
    },
    openAdmin() {
      this.page = 'admin';
      var authAPI = axios.create({ baseURL: API_BASE.replace('/inspection', '/auth') });
      authAPI.get('/organizations').then(r => { this.allOrgs = r.data.data || []; });
      authAPI.get('/users').then(r => { this.allUsers = r.data.data || []; });
    },
    async createUser() {
      var u = this.newUser;
      if (!u.username || !u.password || !u.display_name) { this.adminMsg = '请填写完整信息'; return; }
      if (u.password.length < 4) { this.adminMsg = '密码至少需要4位'; return; }
      try {
        var authAPI = axios.create({ baseURL: API_BASE.replace('/inspection', '/auth') });
        await authAPI.post('/users', u);
        this.adminMsg = '创建成功: ' + u.display_name;
        this.newUser = { username: '', password: '', display_name: '', role: 'lead', org_id: 0 };
        var r = await authAPI.get('/users'); this.allUsers = r.data.data || [];
      } catch(e) { this.adminMsg = '创建失败: ' + this._errMsg(e, '请检查填写信息'); }
    },
    doLogout() { localStorage.removeItem('fire_token'); localStorage.removeItem('fire_user'); sessionStorage.removeItem('fire_token'); sessionStorage.removeItem('fire_user'); window.location.href = '/inspect/web/login.html'; },
    showToast(msg, type='info') {
      this.toast = { msg, type };
      setTimeout(() => { this.toast = null; }, 3000);
    },
    confirmBackToHome() {
      if (this.judgedCount > 0 && !confirm('已判断 ' + this.judgedCount + ' 项，将丢失进度。确定返回？')) return;
      this.wsDisconnect();
      this._removeStickyActionBar();
      this.page = 'home'; var self = this; setTimeout(function() { self.loadActiveInspections(); }, 500); this.inspectionId = ''; this.currentItem = null; this.judgments = {}; this.judgedCount = 0; this.failCount = 0; this.pendingConfirm = false;
    },
    goHomeFromReport() {
      this.wsDisconnect();
      this._removeStickyActionBar();
      this.page = 'home'; var self = this; setTimeout(function() { self.loadActiveInspections(); }, 500);
    },
    async viewLastReport() {
      var id = this.inspectionId || localStorage.getItem('fire_last_inspection_id');
      if (!id) return;
      try {
        this.inspectionId = id;
        await this.generateReport();
        this.page = 'report';
      } catch(e) { this.showToast('报告加载失败', 'error'); }
    },
    categoryLabel(cat) {
      return { '消防管理': '管理', '技术条件': '技术', '设施完好': '设施' }[cat] || cat;
    },
    getRiskColor(h) {
      if (!h.fail_count) return 'green';
      if (h.important_fail_count >= 3) return 'red';
      if (h.important_fail_count >= 1) return 'orange';
      return 'yellow';
    },
    getPhotoGuide(facility) {
      var guides = {
        '防火门': '📸 建议拍摄: ①门扇侧面铭牌(确认甲/乙/丙级) ②闭门器特写 ③门扇全貌+密封条',
        '灭火器': '📸 建议拍摄: ①压力表特写(看指针绿区) ②瓶体铭牌(看有效期) ③整体照片',
        '消火栓': '📸 建议拍摄: ①箱内全景(水带水枪) ②阀门接口特写 ③检查记录卡',
        '疏散通道': '📸 建议拍摄: ①通道全景(看是否畅通) ②宽度标识 ③应急灯+疏散标志',
        '安全出口': '📸 建议拍摄: ①出口门全景 ②门锁状态 ③指示灯状态',
        '应急照明': '📸 建议拍摄: ①灯具全景 ②测试按钮特写 ③电源线状态',
        '喷淋': '📸 建议拍摄: ①喷头正面(看是否遮挡) ②喷头细节(看损坏) ③管道全景',
        '火灾报警': '📸 建议拍摄: ①控制器面板特写 ②探测器外观 ③接线状态',
        '电气线路': '📸 建议拍摄: ①线路全景 ②接头/开关特写 ③穿墙处防火封堵',
        '消防控制室': '📸 建议拍摄: ①控制室全景 ②设备运行状态 ③值班记录表',
      };
      for (var k in guides) {
        if (facility && facility.indexOf(k) >= 0) return guides[k];
      }
      return '📸 建议从不同角度再拍一张补充细节';
    },
    getTypicalHazard(facility) {
      return getTypicalHazard(facility);
    },
    getOperationGuide(facility) {
      return getOperationGuide(facility);
    },

    // === 导航 ===
    // itemsCache: 本地缓存全部检查项（避免每次跳转请求 API）
    async preloadItems() {
      // 一次请求加载全部检查项（替代逐个请求）
      if (this._itemsCache && Object.keys(this._itemsCache).length >= this.totalItems) return;
      try {
        const r = await API.get(`/${this.inspectionId}/items`);
        const all = r.data.data || [];
        this._itemsCache = this._itemsCache || {};
        for (const item of all) {
          this._itemsCache[item.item_index] = item;
        }
      } catch(e) { console.error('preload failed:', e); }
    },
    async goToItem(index) {
      this._updateStickyActionBar();
      if (index < 0) return;
      if (index >= this.totalItems) {
        if (this.judgedCount >= this.totalItems) { this.completeInspection(); }
        return;
      }
      // 优先从缓存读取，缓存未命中才请求 API
      let item = this._itemsCache && this._itemsCache[index];
      if (!item) {
        try {
          const r = await API.get(`/${this.inspectionId}/item/${index}`);
          item = r.data.data;
          if (!this._itemsCache) this._itemsCache = {};
          this._itemsCache[index] = item;
        } catch (e) { console.error(e); return; }
      }
      this.currentItem = item;
      this.currentIndex = index;
      // Section header
      const secName = this.getSectionName(this.currentItem) || '';
      this.currentSectionName = secName;
      this.currentStepName = this.currentItem.step_name || '';
      this._lastSectionName = secName;
      this.showDetail = false;
      this.showQaAnswer = false;
      this.selectedBrand = '';
      this.showOpGuide = false;
      this.recheckPhoto = null;
    },
    async goPrev() { if (this.currentIndex > 0) await this.goToItem(this.currentIndex - 1); },
    async goNext() {
      if (this.currentIndex < this.totalItems - 1) {
        await this.goToItem(this.currentIndex + 1);
      } else {
        // 已在最后一项，检查是否全部判定完毕
        if (this.judgedCount >= this.totalItems) {
          this.completeInspection();
        } else {
          this.showToast(`还有 ${this.totalItems - this.judgedCount} 项未判定，请逐项完成`, 'info');
        }
      }
    },

    // === 历史搜索 ===
    async searchHistory() {
      if (!this.searchVenue) return;
      try {
        const r = await API.get('/search', { params: { venue_name: this.searchVenue } });
        this.historyList = r.data.data || [];
        this.searched = true;
      } catch (e) { console.error(e); }
    },

    // === 开始检查 ===
    startInspection(scene) {
      this.pendingScene = scene;
      // 非公众聚集场所不适用开业前检查
      if (!scene.preopen) this.inspectType = 'daily';
      // 九小场所: 跳过规模参数，直接选子类型
      if (scene.key === 'nine_small') {
        this.showSubTypePicker = true;
        this.showScaleInput = false;
        this.selectedSubType = '';
        this.scaleForm = { area: '100', staff: '3', floors: '1', buildings: '1' };
      } else {
        this.showSubTypePicker = false;
        this.showScaleInput = true;
      this.selectedLeadId = (this.currentUser && this.currentUser.id) || 0;
      this.selectedAssistId = 0;
      if (this.currentUser && this.currentUser.org_id) {
        axios.get(API_BASE.replace("/inspection", "/auth") + "/users?org_id=" + this.currentUser.org_id).then(r => { this.orgUsers = r.data.data || []; }).catch(() => {});
      }
        this.selectedSubType = '';
        this.scaleForm = { area: '', staff: '', floors: '', buildings: '1' };
      }
    },
    async confirmStartInspection() {
      const s = this.scaleForm;
      const scene = this.pendingScene;
      const params = {
        venue_type: scene.key,
        inspection_type: this.inspectType,
        location: this.scaleForm.venueName || '', venue_address: this.scaleForm.venueAddress || '',
        org_id: (this.currentUser && this.currentUser.org_id) || 0,
        lead_id: this.selectedLeadId || (this.currentUser && this.currentUser.id) || 0,
        assist_id: this.selectedAssistId || 0,
        lead_id: this.selectedLeadId || (this.currentUser && this.currentUser.id) || 0,
        assist_id: this.selectedAssistId || 0,
        inspector: '消防员',
        staff_count: parseInt(s.staff) || 0,
        floor_count: parseInt(s.floors) || 0,
        area_sqm: parseInt(s.area) || 0,
        building_count: parseInt(s.buildings) || 1,
        sub_type: this.selectedSubType,
      };
      try {
        this.loading = true; this.loadingText = '正在生成检查项...';
        const r = await API.post('/start', params);
        this.loading = false;
        const d = r.data.data;
        this.inspectionId = d.inspection_id;
        this.totalItems = d.total_items;
        this.currentIndex = 0;
        this.$nextTick(function() { this._renderStickyActionBar(); });
        this.inspected = false;
        this.failCount = 0;
        this.judgedCount = 0;
        this.judgments = {};
        this.hasAssistant = !!(this.selectedAssistId && this.selectedAssistId > 0);
        if (this.hasAssistant) {
          var self = this;
          setTimeout(function() { self.wsConnect(); }, 500);
        }
        this.samplingInfo = { staff: d.staff_sample, floor: d.floor_sample };
        this.showScaleInput = false;
        this.showSubTypePicker = false;
        this.page = 'inspect';
        await this.goToItem(0);
        // 后台预加载剩余检查项（不阻塞首屏）
        this.preloadItems();
      } catch (e) { this.loading = false; this.showToast('启动检查失败: ' + e.message, 'error'); }
    },

    async previewRecheck(h) {
      // 直接启动复查（跳过无模板的 recheckPreview）
      if (!confirm('确定基于「' + (h.venue_name || h.location) + '」的检查结果启动复查？\n\n将仅检查上次不合格项')) return;
      await this.startRecheck({ inspection_id: h.inspection_id || h.id });
    },
    async startRecheck(history) {
      try {
        const r = await API.post('/recheck', { previous_inspection_id: history.inspection_id, inspector: '消防员' });
        const d = r.data.data;
        this.inspectionId = d.inspection_id;
        this.totalItems = d.total_items;
        this.currentIndex = 0;
        this.$nextTick(function() { this._renderStickyActionBar(); });
        this.inspected = false;
        this.failCount = 0;
        this.judgedCount = 0;
        this.judgments = {};
        this.page = 'inspect';
        await this.goToItem(0);
        this.preloadItems();
      } catch (e) { this.showToast('启动复查失败: ' + e.message, 'error'); }
    },

    // === 提交判断（可覆盖之前的结果） ===
    async judge(result, note, rectificationStatus) {
      const wasJudged = this.judgments[this.currentIndex] !== undefined;
      const wasFail = wasJudged && this.judgments[this.currentIndex].result === 'fail';
      const wasNA = wasJudged && this.judgments[this.currentIndex].result === 'na';


      if (result === 'fail') {
        // AI或其他来源已提供note→直接使用; 否则弹窗填写
        if (note && note.trim()) {
          // note already provided, use as-is
        } else {
          var existingNote = this.judgments[this.currentIndex]?.note || '';
          note = prompt('请填写问题描述:', existingNote) || '';
        }
        this.diagnosis = this.getDiagnosis(this.currentItem);
        this.showDiagnosis = true;
      } else if (result === 'na') {
        note = '不涉及';
        this.showDiagnosis = false;
        this.diagnosis = null;

        // 确保全部检查项已缓存，然后纯本地跳过同子章节
        await this.preloadItems();
        const currentSection = this.getSectionGroup(this.currentItem);
        const currentStep = this.currentItem?.step || 0;
        let skipEnd = this.currentIndex + 1;

        // 从缓存中找到第一个不同子章节的项（同subsection且同step时跳过）
        while (skipEnd < this.totalItems) {
          const nextItem = this._itemsCache && this._itemsCache[skipEnd];
          if (!nextItem) { skipEnd++; continue; }
          const nextSection = this.getSectionGroup(nextItem);
          const nextStep = nextItem.step || 0;
          // 日常检查: 按 step 分组跳过；开业前检查: 按 subsection 分组跳过
          if (this.inspectType === 'daily') {
            if (nextStep !== currentStep) break;
          } else {
            if (nextSection !== currentSection) break;
          }
          skipEnd++;
        }

        // 批量标记中间项为 N/A（并行发 API）
        const skipCount = skipEnd - this.currentIndex - 1;
        const judgePromises = [];
        for (let i = this.currentIndex + 1; i < skipEnd; i++) {
          this.judgments[i] = { result: 'na', note: '自动跳过' };
          judgePromises.push(
            API.post(`/${this.inspectionId}/judge`, {
              item_index: i, result: 'na', note: '自动跳过', judge_source: 'manual'
            }).catch(() => {})
          );
        }
        await Promise.all(judgePromises);

        this.judgedCount += skipCount + (wasJudged ? 0 : 1);
        this.judgments[this.currentIndex] = { result, note };

        // 跳转到第一个不同章节的项，或完成检查
        if (skipEnd < this.totalItems) {
          await this.goToItem(skipEnd);
        } else {
          this.completeInspection();
        }
        return;
      } else {
        this.showDiagnosis = false;
        this.diagnosis = null;
      }

      try {
        await API.post(`/${this.inspectionId}/judge`, { item_index: this.currentIndex, result, note, judge_source: 'manual' });
        // WS: 通知协办端
        this.wsSend({ type: 'judgment', item_index: this.currentIndex, result: result, note: note, from_role: this.currentUser?.role || 'lead' });
      } catch (e) { console.error(e); }

      // 更新本地记录
      if (!wasJudged) this.judgedCount++;
      this._updateStickyActionBar();
      if (wasFail && result !== 'fail') this.failCount = Math.max(0, this.failCount - 1);
      if (!wasFail && result === 'fail') this.failCount++;
      if (wasNA && result !== 'na' && !wasFail) this.failCount = Math.max(0, this.failCount);
      // N/A items don't count as fail

      this.judgments[this.currentIndex] = { result, note };

      // 自动跳到下一项，或完成检查
      if (this.currentIndex < this.totalItems - 1) {
        await this.goToItem(this.currentIndex + 1);
      } else {
        this.completeInspection();
      }
    },

    // === 智能诊断 ===
    getDiagnosis(item) {
      const map = {
        '消火栓': { causes: ['水泵扬程不足','管网漏水','阀门未全开','水池水位过低','稳压泵故障','管道气堵'], impacts: ['自动喷水灭火系统','消防水炮系统'], fixes: ['立即检查水泵运行状态和出口压力','巡查管网是否有明漏','检查阀门启闭状态和水池水位'] },
        '喷淋': { causes: ['报警阀关闭','水泵故障','管网漏水','末端试水阀未关','水源不足'], impacts: ['火灾自动报警系统(水流指示器)'], fixes: ['检查报警阀组前后阀门','启动水泵看压力','检查末端试水装置'] },
        '报警': { causes: ['探测器污染或老化','线路断路/短路','控制器主板故障','接地不良','电源模块损坏'], impacts: ['联动控制系统','消防广播','防火卷帘联动'], fixes: ['清洁或更换探测器','检查信号线路','测量系统接地电阻'] },
        '防火门': { causes: ['闭门器弹簧失效','门扇变形','顺序器卡死','门框未灌浆'], impacts: ['防火分区完整性','疏散通道安全'], fixes: ['更换闭门器','调整门扇铰链','维修顺序器'] },
        '疏散': { causes: ['堆放杂物','门锁损坏','指示灯故障','宽度设计不足'], impacts: ['人员安全疏散','消防救援通道'], fixes: ['立即清理疏散通道','修复门锁','增设疏散指示标志'] },
        '应急': { causes: ['蓄电池老化','充电模块故障','光源损坏','线路故障'], impacts: ['疏散照明','安全出口指示'], fixes: ['更换蓄电池','检查充电电路','更换损坏光源'] },
        '灭火器': { causes: ['失压(泄漏)','过期未检修','瓶体腐蚀','保险销丢失'], impacts: ['初期火灾扑救能力'], fixes: ['重新充装或更换','定期检修','更新配置'] },
        '控制室': { causes: ['值班脱岗','无证上岗','设备处于手动状态','记录不完整'], impacts: ['火灾自动报警系统','消防联动控制','应急响应'], fixes: ['落实双人持证值班','设备保持自动状态','完善值班记录'] },
        '电气': { causes: ['线路老化','过载','未穿管保护','接线端子松动','私拉乱接'], impacts: ['电气火灾风险','消防设备供电'], fixes: ['更换老化线路','增设穿管保护','规范接线'] },
        '排烟': { causes: ['风机电机故障','风道堵塞','防火阀关闭','控制模块损坏'], impacts: ['人员疏散安全','火灾蔓延控制'], fixes: ['检修风机电机','清理风道','检查防火阀状态'] },
        '卷帘': { causes: ['电机故障','导轨卡阻','控制模块损坏','下方堆放物品'], impacts: ['防火分区完整性'], fixes: ['检修电机','清理导轨','清除下方障碍物'] },
      };
      for (const [k, v] of Object.entries(map)) {
        if (item.facility && item.facility.includes(k)) return v;
      }
      return { causes: ['需要进一步现场排查'], impacts: [], fixes: ['根据现场情况制定整改方案'] };
    },
    closeDiagnosis() { this.showDiagnosis = false; this.diagnosis = null; },

    // === 检查完成 ===
    completeInspection() {
      // 有协办且未确认 → 提请协办确认
      if (this.hasAssistant && this.wsConnected && !this.pendingConfirm) {
        this.requestConfirm();
        return;
      }
      this.inspected = true;
      this.currentItem = null;
      this.currentSectionName = '';
      this.currentStepName = '';
      this.generateReport();
    },
    async generateReport() {
      try {
        const r = await API.get(`/${this.inspectionId}/report`);
        this.report = r.data.data; localStorage.setItem("fire_last_inspection_id", this.inspectionId);
        var h = JSON.parse(localStorage.getItem("fire_inspection_history") || "[]"); h = h.filter(function(e) { return e.id !== this.inspectionId; }); h.unshift({id: this.inspectionId, name: this.report.venue_name, date: this.report.date, score: this.report.assessment.score, color: this.report.assessment.color, total: this.report.summary.checked, fail: this.report.summary.fail}); if (h.length > 5) h = h.slice(0,5); localStorage.setItem("fire_inspection_history", JSON.stringify(h)); this.inspectionHistory = h;
      } catch (e) {
        console.error('生成报告失败:', e);
        this.showToast('报告生成失败，请稍后重试', 'error');
      }
    },

    // === 视频弹窗 ===
    openVideo(url, title) {
      this.currentVideoUrl = url;
      this.currentVideoTitle = title || '示范视频';
      this.showVideoModal = true;
    },
    closeVideo() {
      this.showVideoModal = false;
      this.currentVideoUrl = '';
      this.currentVideoTitle = '';
    },
    async toggleJumpMenu() {
      this.showJumpMenu = !this.showJumpMenu;
      if (this.showJumpMenu) {
        await this.preloadItems();
        this.buildSectionIndex();
      }
    },
    jumpSearch(v) {
      this.jumpKeyword = v;
      if (!v || !v.trim()) { this.jumpFiltered = null; return; }
      var kw = v.trim().toLowerCase();
      var results = [];
      for (var i = 0; i < this.totalItems; i++) {
        var item = (this._itemsCache && this._itemsCache[i]);
        if (!item) continue;
        if ((item.facility || '').toLowerCase().indexOf(kw) >= 0 || (item.check_point || '').toLowerCase().indexOf(kw) >= 0) {
          results.push({ index: i, facility: item.facility, check_point: item.check_point });
        }
        if (results.length >= 30) break;
      }

      // 如果本地精确匹配结果少于3条，用模糊API补充
      if (results.length < 3) {
        var self = this;
        self.jumpFiltered = results.length > 0 ? results : null;
        var scene = (self._currentSceneKey || 'hotel');
        this.fuzzyAPI.post('/fuzzy-search?text=' + encodeURIComponent(kw) + '&scene=' + scene).then(function(r) {
          var d = r.data;
          if (d.success && d.results && d.results.length > 0) {
            // 合并本地精确结果和API模糊结果，去重
            var seen = {};
            results.forEach(function(x) { seen[x.index] = true; });
            var merged = results.slice();
            d.results.forEach(function(x) {
              if (!seen[x.index] && merged.length < 30) {
                seen[x.index] = true;
                merged.push(x);
              }
            });
            // 按分数排序（API结果有score，本地结果默认1.0）
            merged.sort(function(a, b) { return (b.score || 1.0) - (a.score || 1.0); });
            self.jumpFiltered = merged;
          } else if (results.length === 0) {
            self.jumpFiltered = d.results || [];
          }
        }).catch(function() {
          // API失败时保留本地结果
        });
      } else {
        this.jumpFiltered = results;
      }
    },
    buildSectionIndex() {
      // 从缓存读取（preloadItems 已一次加载全部），不再逐项请求 API
      if (Object.keys(this.sectionIndex).length > 0) return;
      const idx = {};
      let lastSection = ''; let sectionStart = 0;
      for (let i = 0; i < this.totalItems; i++) {
        const item = (this._itemsCache && this._itemsCache[i]);
        if (!item) continue;
        const secName = this.getSectionName(item);
        if (secName && secName !== lastSection && i > 0) {
          if (lastSection) idx[lastSection] = { start: sectionStart, end: i - 1 };
          sectionStart = i;
        }
        if (secName) lastSection = secName;
      }
      if (lastSection) idx[lastSection] = { start: sectionStart, end: this.totalItems - 1 };
      this.sectionIndex = idx;
    },
    judgedInRange(start, end) {
      let c = 0;
      for (let i = start; i <= end; i++) { if (this.judgments[i]) c++; }
      return c;
    },

    _resolvePreopen(item) {
      // 优先使用 API 返回的 preopen_* 字段，否则从 section_order 推导
      if (item?.preopen_section) {
        return { sec: item.preopen_section, grp: item.preopen_group || 0, sub: item.preopen_sub || 0 };
      }
      const order = item?.section_order || item?.preopen_order || 0;
      for (const [lo, hi, s, g, sb] of this.preopenOrderMap) {
        if (order >= lo && order <= hi) return { sec: s, grp: g, sub: sb };
      }
      return { sec: 2, grp: 2, sub: 17 };
    },
    getSectionName(item) {
      const step = item?.step || 0;
      if (this.inspectType === 'daily') {
        const dm = {
          1:'1、消防许可及验收备案', 2:'2、消防安全管理',
          3:'3、建筑防火', 4:'4、安全疏散', 5:'5、消防控制室',
          6:'6、消防设施器材(报警+给水)', 7:'7、消防设施器材(灭火+其他)',
          8:'8、其他消防安全管理'
        };
        return dm[step] || '';
      }
      // 开业前检查三层分组
      const { sec, sub } = this._resolvePreopen(item);
      const secNames = {1:'一、消防安全责任', 2:'二、消防安全技术条件', 3:'三、消防安全管理', 4:'四、其他消防安全事项'};
      const subNames = {1:'1、总平面布局',2:'2、平面布置',3:'3、防火分区及防火分隔',4:'4、安全疏散',
                        5:'5、内部装修',6:'6、消防水源',7:'7、室外消火栓系统和水泵接合器',
                        8:'8、室内消火栓系统',9:'9、自动喷水灭火系统',10:'10、火灾自动报警系统',
                        11:'11、防烟排烟系统',12:'12、消防应急照明和疏散指示标志',13:'13、电气线路',
                        14:'14、灭火器',15:'15、消防电梯',16:'16、消防控制室',17:'17、其他消防设施'};
      if (sub > 0 && subNames[sub]) return secNames[sec] + ' › ' + subNames[sub];
      return secNames[sec] || '';
    },
    // 加载进行中的检查列表
    async loadActiveInspections() {
      try {
        var r = await API.get('/active?include_completed=1');
        var all = r.data.data || [];
        // active = 仅进行中的
        this.activeInspections = all.filter(function(i) { return i.status === 'in_progress'; });
        // 合并完成的到 inspectionHistory（API + localStorage）
        var completed = all.filter(function(i) { return i.status === 'completed'; });
        var localHist = JSON.parse(localStorage.getItem('fire_inspection_history') || '[]');
        var merged = {};
        // API 数据优先，覆盖 localStorage 旧值
        completed.forEach(function(c) {
          merged[c.inspection_id] = {
            id: c.inspection_id, name: c.venue_name,
            date: c.date, score: c.score || 0,
            total: c.total_items, fail: c.fail_count || 0
          };
        });
        // 补充 localStorage 中有但 API 里没有的数据
        localHist.forEach(function(h) {
          if (!merged[h.id]) merged[h.id] = h;
        });
        var hist = Object.values(merged);
        hist.sort(function(a, b) { return (b.date || '').localeCompare(a.date || ''); });
        if (hist.length > 5) hist = hist.slice(0, 5);
        this.inspectionHistory = hist;
        localStorage.setItem('fire_inspection_history', JSON.stringify(hist));
      } catch(e) { this.activeInspections = []; }
    },
    // 协办加入检查
    async joinInspection(insp) {
      try {
        // 加载该检查的信息
        var r = await API.get('/' + insp.inspection_id + '/report');
        var data = r.data.data;
        this.inspectionId = insp.inspection_id;
        this.totalItems = insp.total_items || data.summary.total || 0;
        this.currentIndex = insp.current_index || 0;
        this.judgments = {};
        this.judgedCount = 0;
        this.failCount = 0;
        this.hasAssistant = true;
        this.page = 'inspect';
        await this.goToItem(this.currentIndex);
        this.preloadItems();
        // 连接 WS
        var self = this;
        setTimeout(function() { self.wsConnect(); }, 500);
      } catch(e) {
        this.showToast('加入检查失败: ' + e.message, 'error');
      }
    },

    // === WebSocket 协办 ===
    wsConnect() {
      if (!this.inspectionId || !this.token) return;
      var self = this;
      var protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
      var wsUrl = protocol + '//' + location.host + '/inspect/api/v1/ws/' + this.inspectionId + '?token=' + this.token;
      try {
        var ws = new WebSocket(wsUrl);
        ws.onopen = function() {
          self.wsConnected = true;
          self.wsReconnectDelay = 1000;
          console.log('[WS] Connected to', self.inspectionId);
        };
        ws.onmessage = function(e) {
          try {
            var msg = JSON.parse(e.data);
            self._handleWsMessage(msg);
          } catch(ex) {}
        };
        ws.onclose = function(e) {
          self.wsConnected = false;
          self.ws = null;
          if (e.code !== 1000 && e.code !== 4001 && e.code !== 4003 && e.code !== 4004) {
            // 异常断开，自动重连
            console.log('[WS] Disconnected, reconnecting in', self.wsReconnectDelay + 'ms');
            self.wsReconnectTimer = setTimeout(function() {
              self.wsReconnectDelay = Math.min(self.wsReconnectDelay * 2, 30000);
              self.wsConnect();
            }, self.wsReconnectDelay);
          }
        };
        ws.onerror = function() { /* onclose 会处理 */ };
        self.ws = ws;
      } catch(e) {}
    },
    wsDisconnect() {
      if (this.wsReconnectTimer) { clearTimeout(this.wsReconnectTimer); this.wsReconnectTimer = null; }
      if (this.ws) {
        try { this.ws.close(1000); } catch(e) {}
        this.ws = null;
      }
      this.wsConnected = false;
    },
    wsSend(msg) {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        try { this.ws.send(JSON.stringify(msg)); } catch(e) {}
      }
    },
    _handleWsMessage(msg) {
      var type = msg.type;
      if (type === 'judgment') {
        // 协办端接收主办判定
        if (!this.judgments[msg.item_index]) {
          this.judgedCount++;
      this._updateStickyActionBar();
        }
        this.judgments[msg.item_index] = { result: msg.result, note: msg.note || '' };
        var labels = {pass: '✅ 合格', fail: '❌ 不合格', na: '⊘ 不涉及'};
        var label = labels[msg.result] || msg.result;
        this.showToast((msg.from_role === 'lead' ? '主办' : '协办') + '判定: ' + label + ' (第' + (msg.item_index+1) + '项)', 'info');
      } else if (type === 'photo') {
        this.showToast('📸 ' + (msg.from_role === 'lead' ? '主办' : '协办') + '上传了照片', 'info');
      } else if (type === 'jump') {
        this.goToItem(msg.target_index);
      } else if (type === 'request_confirm') {
        // 协办端：主办提请完成，弹出确认提示
        this.pendingConfirm = true;
        this.showToast('📋 主办已完成检查，请确认', 'info');
      } else if (type === 'confirmed') {
        // 主办端：协办已确认
        this.showToast('✅ 协办已确认', 'info');
        this.completeInspection();
      } else if (type === 'user_joined') {
        this.showToast('👤 ' + msg.display + ' 已加入', 'info');
      } else if (type === 'pong') {
        // 心跳响应
      }
    },
    // 主办提请协办确认
    requestConfirm() {
      this.pendingConfirm = true;
      this.wsSend({
        type: 'request_confirm',
        total_items: this.totalItems,
        judged_count: this.judgedCount,
        fail_count: this.failCount
      });
      this.showToast('已发送确认请求，等待协办确认...', 'info');
    },
    // 协办确认完成
    assistantConfirm() {
      this.pendingConfirm = false;
      this.wsSend({ type: 'confirm' });
      this.completeInspection();
    },

    refreshApp() { window.location.reload(true); },
    _renderStickyActionBar() {
      var self = this;
      var existing = document.getElementById('stickyActionBar');
      if (existing) existing.remove();
      if (!this.currentIndex && this.currentIndex !== 0) return;

      var bar = document.createElement('div');
      bar.id = 'stickyActionBar';
      bar.className = 'sticky-action-bar';

      // Pass button
      var passBtn = document.createElement('button');
      passBtn.className = 'btn-pass' + (this.judgments[this.currentIndex]?.result === 'pass' ? ' active' : '');
      passBtn.textContent = '✅ 合格';
      passBtn.addEventListener('click', function() { self.judge('pass'); });

      // Fail button
      var failBtn = document.createElement('button');
      failBtn.className = 'btn-fail' + (this.judgments[this.currentIndex]?.result === 'fail' ? ' active' : '');
      failBtn.textContent = '❌ 不合格';
      failBtn.addEventListener('click', function() { self.judge('fail'); });

      // NA button
      var naBtn = document.createElement('button');
      naBtn.className = 'btn-na' + (this.judgments[this.currentIndex]?.result === 'na' ? ' active' : '');
      naBtn.textContent = '⊘ 不涉及';
      naBtn.addEventListener('click', function() { self.judge('na'); });

      // Photo button
      var photoBtn = document.createElement('button');
      photoBtn.textContent = '📷';
      photoBtn.style.cssText = 'min-width:44px;background:#1a1a2e;color:#fff;border-color:#1a1a2e';
      photoBtn.addEventListener('click', function() { var orig = document.querySelector('.btn-photo'); if (orig) orig.click(); });

      // Nav info
      var navInfo = document.createElement('span');
      navInfo.className = 'nav-info';
      navInfo.textContent = (this.currentIndex + 1) + '/' + this.totalItems;

      // Prev button
      var prevBtn = document.createElement('button');
      prevBtn.className = 'btn-nav';
      prevBtn.textContent = '◀';
      prevBtn.style.cssText = 'min-width:44px;padding:10px 12px';
      if (this.currentIndex === 0) { prevBtn.disabled = true; prevBtn.style.opacity = '0.4'; }
      prevBtn.addEventListener('click', function() { self.goPrev(); });

      // Next button
      var nextBtn = document.createElement('button');
      nextBtn.className = 'btn-nav';
      nextBtn.textContent = '▶';
      nextBtn.style.cssText = 'min-width:44px;padding:10px 12px';
      if (this.currentIndex >= this.totalItems - 1) { nextBtn.disabled = true; nextBtn.style.opacity = '0.4'; }
      nextBtn.addEventListener('click', function() { self.goNext(); });

      bar.appendChild(prevBtn);
      bar.appendChild(passBtn);
      bar.appendChild(failBtn);
      bar.appendChild(naBtn);
      bar.appendChild(photoBtn);
      bar.appendChild(navInfo);
      // ▶ removed: judge() auto-advances, double-click would skip items
      // bar.appendChild(nextBtn);

      document.body.appendChild(bar);
    },
    _updateStickyActionBar() {
      var bar = document.getElementById('stickyActionBar');
      if (!bar || !this.currentIndex && this.currentIndex !== 0) return;

      // Update pass/fail/na active states
      var buttons = bar.querySelectorAll('button');
      var result = this.judgments[this.currentIndex]?.result || '';
      for (var i = 0; i < buttons.length; i++) {
        var btn = buttons[i];
        var text = btn.textContent;
        if (text.includes('合格')) {
          btn.className = 'btn-pass' + (result === 'pass' ? ' active' : '');
        } else if (text.includes('不合格')) {
          btn.className = 'btn-fail' + (result === 'fail' ? ' active' : '');
        } else if (text.includes('不涉及')) {
          btn.className = 'btn-na' + (result === 'na' ? ' active' : '');
        }
      }

      // Update nav info
      var navInfo = bar.querySelector('.nav-info');
      if (navInfo) navInfo.textContent = (this.currentIndex + 1) + '/' + this.totalItems;

      // Update prev/next disabled states
      var navBtns = bar.querySelectorAll('.btn-nav');
      if (navBtns[0]) { navBtns[0].disabled = this.currentIndex === 0; navBtns[0].style.opacity = this.currentIndex === 0 ? '0.4' : '1'; }
    },
    _removeStickyActionBar() {
      var bar = document.getElementById('stickyActionBar');
      if (bar) bar.remove();
    },
    _renderOwnerReviewModal() {
      var self = this;
      var existing = document.getElementById('ownerReviewModal');
      if (existing) existing.remove();
      if (!this.ownerReviewDetail || !this.ownerReviewDetail.checklist) return;

      var detail = this.ownerReviewDetail;
      var modal = document.createElement('div');
      modal.id = 'ownerReviewModal';
      modal.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.5);z-index:9999;display:flex;align-items:flex-end;justify-content:center;font-family:-apple-system,PingFang SC,Microsoft YaHei,sans-serif';
      modal.addEventListener('click', function(e) { if (e.target === modal) self._hideOwnerReviewModal(); });

      var inner = document.createElement('div');
      inner.style.cssText = 'width:100%;max-width:600px;max-height:85vh;background:#f0f2f5;border-radius:16px 16px 0 0;overflow:hidden;display:flex;flex-direction:column';

      // Header
      var header = document.createElement('div');
      header.style.cssText = 'background:#1a1a2e;color:#fff;padding:16px;text-align:center;flex-shrink:0';
      header.innerHTML = '<div style=\'font-size:16px;font-weight:700\'>' + (detail.submission?.venue_name || '') + '</div><div style=\'font-size:11px;opacity:.7\'>' + (detail.submission?.venue_type || '') + ' · ' + ((detail.submission?.created_at || '').substring?.(0,10) || '') + '</div>';
      inner.appendChild(header);

      // Scrollable list
      var list = document.createElement('div');
      list.style.cssText = 'overflow-y:auto;flex:1;padding:8px 0';

      var checklist = detail.checklist || [];
      var ownerItems = detail.owner_items || [];
      for (var i = 0; i < checklist.length; i++) {
        var item = checklist[i];
        var oi = ownerItems[i] || {};
        if (!oi.result) continue; // Skip unchecked items

        var card = document.createElement('div');
        card.style.cssText = 'margin:6px 12px;padding:12px;background:#fff;border:1px solid #e5e5e5;border-radius:8px;font-size:13px';

        var resultEmoji = oi.result === 'pass' ? '✅' : oi.result === 'fail' ? '❌' : '⬜';
        var resultColor = oi.result === 'pass' ? '#16a34a' : oi.result === 'fail' ? '#dc2626' : '#999';

        var html = '<div style=\'display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:4px\'>' +
          '<div style=\'flex:1;min-width:0\'>' +
            '<div style=\'font-weight:600;margin-bottom:2px\'>' + (item.facility || item.title || '') + '</div>' +
            '<div style=\'font-size:11px;color:#8899aa\'>' + (item.check_point || '') + '</div>' +
          '</div>' +
          '<span style=\'font-size:11px;padding:2px 8px;border-radius:10px;background:' + (oi.result === 'pass' ? '#e8f5e9' : '#ffebee') + ';color:' + resultColor + ';white-space:nowrap;margin-left:8px\'>' + resultEmoji + ' ' + (oi.result === 'pass' ? '合格' : '不合格') + '</span>' +
        '</div>';

        if (oi.note) {
          html += '<div style=\'font-size:11px;color:#666;margin-top:4px;padding:4px 8px;background:rgba(0,0,0,.03);border-radius:4px\'>📝 ' + oi.note + '</div>';
        }

        if (oi.photos && oi.photos.length) {
          html += '<div style=\'display:flex;gap:6px;margin-top:6px;flex-wrap:wrap\'>';
          for (var j = 0; j < oi.photos.length; j++) {
            var p = oi.photos[j];
            html += '<img src=\'data:' + p.type + ';base64,' + p.data + '\' style=\'width:80px;height:80px;object-fit:cover;border-radius:4px;border:1px solid #ddd;cursor:pointer\' onclick=\'window.open(this.src)\'>';
          }
          html += '</div>';
        }

        card.innerHTML = html;
        list.appendChild(card);
      }

      // Show summary if no items checked
      if (list.children.length === 0) {
        var empty = document.createElement('div');
        empty.style.cssText = 'text-align:center;padding:40px;color:#999;font-size:14px';
        empty.textContent = '📭 该业主尚未自查任何项目';
        list.appendChild(empty);
      }

      inner.appendChild(list);

      // Bottom buttons
      var bottom = document.createElement('div');
      bottom.style.cssText = 'padding:12px 16px;background:#fff;border-top:1px solid #e5e5e5;display:flex;gap:10px;flex-shrink:0';

      var returnBtn = document.createElement('button');
      returnBtn.style.cssText = 'flex:1;padding:12px;background:#fff;color:#e65100;border:1px solid #e65100;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer';
      returnBtn.textContent = '↩ 退回修改';
      returnBtn.addEventListener('click', function() { self.returnOwnerSubmission(detail.submission.code); });

      var approveBtn = document.createElement('button');
      approveBtn.style.cssText = 'flex:1;padding:12px;background:#16a34a;color:#fff;border:none;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer';
      approveBtn.textContent = '✅ 审核通过';
      approveBtn.addEventListener('click', function() { self.approveOwnerSubmission(detail.submission.code); });

      bottom.appendChild(returnBtn);
      bottom.appendChild(approveBtn);
      inner.appendChild(bottom);

      modal.appendChild(inner);
      document.body.appendChild(modal);
    },
    _hideOwnerReviewModal() {
      var existing = document.getElementById('ownerReviewModal');
      if (existing) existing.remove();
      this.showOwnerReview = false;
    },
    async deleteInspection(inspId) {
      if (!confirm('确认删除该检查？')) return;
      this.activeInspections = this.activeInspections.filter(function(x) { return x.inspection_id !== inspId; });
      try {
        await API.delete('/' + inspId);
      } catch(e) { this.showToast('删除失败', 'error'); }
    },
    async deleteOwnerSubmission(code) {
      if (!confirm('确认删除该业主提交？')) return;
      this.ownerSubmissions = this.ownerSubmissions.filter(function(x) { return x.code !== code; });
      try {
        await API.delete('/../owner/submissions/' + code);
      } catch(e) { this.showToast('删除失败', 'error'); }
    },
    // === 业主自查管理 ===
    async loadOwnerSubmissions() {
      try {
        var r = await API.get('/owner-submissions');
        this.ownerSubmissions = r.data.data || [];
        this.showOwnerCard = true;
      } catch(e) { this.ownerSubmissions = []; }
    },
    async createOwnerLink() {
      var o = this.ownerNewLink;
      if (!o.venue_name) { this.showToast('请填写场所名称', 'error'); return; }
      try {
        var r = await API.post('/../owner/create-link', null, {
          params: { venue_type: o.venue_type, venue_name: o.venue_name, venue_address: o.venue_address, inspector_id: this.currentUser?.id || 0, org_id: this.currentUser?.org_id || 0 }
        });
        var d = r.data.data;
        this.ownerNewCode = d.code;
        this.ownerNewLinkUrl = d.full_url;
        this.showToast('链接已生成，可复制发给业主', 'info');
        await this.loadOwnerSubmissions();
      } catch(e) { this.showToast('创建失败', 'error'); }
    },
    copyOwnerLink() {
      var input = document.createElement('input');
      input.value = this.ownerNewLinkUrl;
      document.body.appendChild(input);
      input.select();
      document.execCommand('copy');
      document.body.removeChild(input);
      this.showToast('链接已复制', 'info');
    },
    async reviewOwnerDetail(code) {
      try {
        var r = await API.get('/../owner/submissions/' + code);
        this.ownerReviewDetail = r.data.data;
        this.showOwnerReview = true;
        this.$nextTick(function() {
          this._renderOwnerReviewModal();
        });
      } catch(e) { this.showToast('加载详情失败', 'error'); }
    },
    async approveOwnerSubmission(code) {
      try {
        await API.post('/../owner/submissions/' + code + '/review', null, {params:{status:'reviewed'}});
        this.showToast('已审核通过', 'info');
        this._hideOwnerReviewModal();
        await this.loadOwnerSubmissions();
      } catch(e) { this.showToast('操作失败', 'error'); }
    },
    async returnOwnerSubmission(code) {
      var reason = prompt('请输入退回原因（业主可见）：');
      if (reason === null) return;
      try {
        await API.post('/../owner/submissions/' + code + '/return', null, {params:{reason:reason}});
        this.showToast('已退回', 'info');
        this._hideOwnerReviewModal();
        await this.loadOwnerSubmissions();
      } catch(e) { this.showToast('操作失败', 'error'); }
    },
    async reviewOwner(code) {
      await this.reviewOwnerDetail(code);
    },
    async openDashboard() {
      this.page = 'dashboard';
      try {
        var r = await API.get('/stats');
        this.dashboard = r.data.data || null;
      } catch(e) { this.dashboard = null; this.showToast('加载统计数据失败', 'error'); }
    },
    async loadStats() {
      try {
        var r = await API.get('/stats');
        this.dashboard = r.data.data || null;
      } catch(e) {}
    },
    downloadPDF() {
      var url = API_BASE + '/' + this.inspectionId + '/report/export?format=html';
      var w = window.open(url, '_blank');
      if (w) {
        var self = this;
        setTimeout(function() { w.print(); self.showToast('💡 在打印对话框中选「另存为 PDF」即可保存', 'info'); }, 1500);
      } else {
        this.showToast('请允许弹出窗口后重试', 'error');
      }
    },
    printReport() { this.downloadPDF(); },
    downloadExcel() {
      var url = API_BASE + '/' + this.inspectionId + '/report/export?format=excel';
      var a = document.createElement('a');
      a.href = url;
      a.download = this.inspectionId + '.xlsx';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      this.showToast('Excel 报告下载中...', 'info');
    },
    getSectionGroup(item) {
      if (this.inspectType === 'daily') return item?.step || 0;
      const { sec, sub } = this._resolvePreopen(item);
      return sec * 100 + sub;
    },
    getQaReference(item) {
      const map = {
        '责任制': '参考答案:\n1. 是否建立了从单位负责人→部门负责人→岗位员工的三级责任制\n2. 是否签订消防安全责任书，明确各岗位职责\n3. 是否将消防安全纳入绩效考核\n4. 现场抽问2名员工，确认其知晓本岗位消防职责',
        '责任人': '参考答案:\n1. 消防安全责任人应为法定代表人/主要负责人/实际控制人\n2. 消防安全管理人宜具有注册消防工程师资格\n3. 核查是否了解消防法律法规和本单位消防重点部位\n4. 询问最近一次防火检查情况和整改落实结果',
        '预案': '参考答案:\n1. 预案是否包含:组织机构、火情报告、处置程序、疏散措施、灭火措施、通讯联络、安全防护\n2. 是否每半年至少组织一次演练\n3. 抽查2名员工:是否知晓本岗位的应急任务\n4. 核查最近一次演练记录和照片',
        '巡查': '参考答案:\n1. 公众聚集场所营业期间:每2小时至少巡查一次\n2. 医院/养老院/寄宿学校:夜间每2小时巡查一次\n3. 巡查记录应包含:巡查时间、部位、内容、发现问题、处理结果\n4. 最近一个月巡查记录是否完整、问题是否闭环',
        '培训': '参考答案:\n1. 新员工上岗前是否经过消防安全培训\n2. 全体员工每半年至少一次消防培训\n3. 抽查2名员工"一懂三会":懂火灾危险性、会报警、会扑救初起火灾、会逃生自救\n4. 查阅培训记录和签到表',
      };
      for (const [k, v] of Object.entries(map)) {
        if (item.facility && item.facility.includes(k)) return v;
        if (item.check_point && item.check_point.includes(k)) return v;
      }
      return '参考答案:\n根据相关法规要求，现场核实后判断是否符合规定。如有疑问可拍照上传辅助判断。';
    },

    // === 计算工具 ===
    openCalc(type) {
      this.showCalc = true; this.calcType = type; this.calcResult = null;
      this.calcInput = { area: '', floors: '1', floor: '1', people: '', sprinkler: true, highrise: false, level: '中危险级' };
    },
    calcTitle() {
      return {'fire_zone':'防火分区面积验算','water_tank':'消防水池有效容积','evacuation':'疏散宽度核算','extinguisher':'灭火器配置验算'}[this.calcType] || '计算工具';
    },
    async runCalc() {
      try {
        const r = await API.post(`/calc/${this.calcType}`, this.calcInput);
        this.calcResult = r.data?.data || r.data;
      } catch (e) { this.calcResult = { result: '计算失败: ' + (e.response?.data?.msg || e.message) }; }
    },

    // (photo/report/voice 方法委托到 APP_EXTRAS — 见 app-extras.js)
    uploadPhoto(e) { APP_EXTRAS.uploadPhoto.call(this, e); },
    confirmPhotoResult() { APP_EXTRAS.confirmPhotoResult.call(this); },
    uploadRecheckPhoto(e) { APP_EXTRAS.uploadRecheckPhoto.call(this, e); },
    viewReport() { return APP_EXTRAS.viewReport.call(this); },
    newInspection() { APP_EXTRAS.newInspection.call(this); },
    viewOwnerReport() { return APP_EXTRAS.viewOwnerReport.call(this); },
    printOwnerReport() { APP_EXTRAS.printOwnerReport.call(this); },
    printReport() {
      window.print();
    },

    // (voice/search 方法委托到 APP_EXTRAS — 见 app-extras.js)
    startSearch() { APP_EXTRAS.startSearch.call(this); },
    doSearch() { return APP_EXTRAS.doSearch.call(this); },
    voiceAvailable() { return APP_EXTRAS.voiceAvailable(); },
    voiceUnavailableReason() { return APP_EXTRAS.voiceUnavailableReason(); },
    startVoice() { return APP_EXTRAS.startVoice.call(this); },
    stopVoice() { APP_EXTRAS.stopVoice.call(this); },
     
    async startVoiceJudge() {
      if (this.isVoiceJudging) { this.stopVoiceJudge(); return; }
      this.voiceJudgeText = '🎤 正在启动...';
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        this._voiceStream = stream;
        const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : 'audio/webm';
        const recorder = new MediaRecorder(stream, { mimeType });
        const chunks = [];
        recorder.ondataavailable = function(e) { if (e.data.size > 0) chunks.push(e.data); };
        recorder.onstart = () => { this.isVoiceJudging = true; this.voiceJudgeText = '🎤 正在聆听...'; };
        recorder.onstop = async () => {
          this.isVoiceJudging = false; this.voiceJudgeText = '';
          stream.getTracks().forEach(function(t) { t.stop(); });
          if (chunks.length === 0) { this.voiceJudgeText = '⚠️ 未录制到音频，请重试'; return; }
          const blob = new Blob(chunks, { type: mimeType });
          this.voiceJudgeText = '🎧 识别中...';
          try {
            const form = new FormData();
            form.append('file', blob, 'judge.' + (mimeType.includes('mp4') ? 'mp4' : 'webm'));
            const speechAPI = axios.create({ baseURL: API_BASE.replace('/inspection', '/speech') });
            const r = await speechAPI.post('/transcribe', form);
            const text = r.data?.text || r.data?.transcript || '';
            if (text.trim()) { this._parseVoiceJudgment(text); }
            else { this.voiceJudgeText = '⚠️ 未识别到语音内容，请重试'; }
          } catch (e) { this.voiceJudgeText = '⚠️ 识别失败: ' + (e.message || '网络错误'); }
        };
        this._voiceRecorder = recorder;
        recorder.start();
        setTimeout(() => { if (this.isVoiceJudging) this.stopVoiceJudge(); }, 15000);
      } catch (e) {
        this.isVoiceJudging = false;
        if (e.name === 'NotAllowedError') { this.voiceJudgeText = '⚠️ 麦克风权限未开启'; }
        else if (e.name === 'NotFoundError') { this.voiceJudgeText = '⚠️ 未找到麦克风设备'; }
        else { this.voiceJudgeText = '⚠️ 录音失败: ' + (e.message || ''); }
      }
    },
    stopVoiceJudge() {
      if (this._voiceRecorder && this._voiceRecorder.state === 'recording') this._voiceRecorder.stop();
      if (this._voiceStream) this._voiceStream.getTracks().forEach(function(t) { t.stop(); });
      this.isVoiceJudging = false;
    },
    _parseVoiceJudgment(text) {
      var t = text.trim();
      var result, note = '';

      // 第一层：精确中文正则（保留原逻辑，零延迟）
      if (/合格|没问题|正常|符合|通过|合规/.test(t) && !/不/.test(t)) { result = 'pass'; note = t; }
      else if (/不合格|有问题|不行|隐患|过期|损坏|缺失|堵塞|故障|失效/.test(t)) { result = 'fail'; note = t.replace(/不合格[，。,.\s]*/, '').replace(/有问题[，。,.\s]*/, ''); if (!note.trim()) note = t; }
      else if (/跳过|不涉及|N\/?A/.test(t)) { result = 'na'; note = '不涉及'; }
      else if (/拍照|拍个照/.test(t)) { this.voiceJudgeText = '📸 请拍照'; setTimeout(() => { this.showPhoto = true; this.voiceJudgeText = ''; }, 500); return; }
      else { result = null; }

      if (result) {
        this.voiceJudgeText = '';
        this.judge(result, note);
        return;
      }

      // 第二层：拼音模糊匹配（处理口音/识别错误，~200ms）
      var self = this;
      this.voiceJudgeText = '🔍 正在理解...';
      this.fuzzyAPI.post('/fuzzy-judge?text=' + encodeURIComponent(t)).then(function(r) {
        var d = r.data;
        if (d.success && d.action !== 'unknown' && d.confidence >= 0.4) {
          self.voiceJudgeText = '';
          if (d.action === 'photo') {
            self.showPhoto = true;
          } else if (d.action === 'skip') {
            self.judge('na', '不涉及');
          } else if (d.action === 'pass') {
            self.judge('pass', d.note || t);
          } else if (d.action === 'fail') {
            self.judge('fail', d.note || t);
          }
        } else {
          self.voiceJudgeText = '🤔 无法识别: "' + t + '" 请说"合格"/"不合格"/"有隐患"等';
        }
      }).catch(function() {
        self.voiceJudgeText = '🤔 无法识别: "' + t + '"';
      });
    },

  },
}).mount('#app');
