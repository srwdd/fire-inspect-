const { createApp } = Vue;
const API_BASE = window.location.pathname.includes('/inspect') ? '/inspect/api/v1/inspection' : '/api/v1/inspection';
const API = axios.create({ baseURL: API_BASE });

const SCENES = [
  { key: 'hotel', name: '宾馆/酒店', icon: '🏨', preopen: true },
  { key: 'mall', name: '商场/市场', icon: '🏬', preopen: true },
  { key: 'entertainment', name: '公共娱乐场所', icon: '🎤', preopen: true },
  { key: 'school', name: '学校/幼儿园', icon: '🏫', preopen: false },
  { key: 'hospital', name: '医院', icon: '🏥', preopen: false },
  { key: 'elderly', name: '养老机构', icon: '🧓', preopen: false },
  { key: 'restaurant', name: '餐饮场所', icon: '🍽️', preopen: true },
  { key: 'highrise', name: '高层建筑', icon: '🏢', preopen: false },
  { key: 'mixed_use', name: '多业态混合', icon: '🏗️', preopen: false },
  { key: 'factory', name: '厂房/仓库', icon: '🏭', preopen: false },
  { key: 'crowded', name: '人员密集场所', icon: '👥', preopen: false },
  { key: 'nine_small', name: '九小场所', icon: '🏪', preopen: false },
];

// 设施操作测试指南（现场测试用）
const OPERATION_GUIDES = {
  '消火栓系统': {
    question: '请现场测试室内消火栓的出水压力和启泵功能',
    steps: ['打开消火栓箱门（箱门开启角度≥160°）','检查箱内器材：水枪×1、水带×1（25m）、栓阀','展开水带，连接水枪和栓阀接口','逆时针旋转手轮全开栓阀','握紧水枪对准排水方向，观察充实水柱（一般≥10m，高层≥13m）','按下消火栓箱内启泵按钮','到消防控制室确认：控制器收到启泵反馈信号，水泵30秒内启动'],
    passCriteria: '水压充足、充实水柱达标、启泵按钮有效、控制室收到信号',
    video: '',
  },
  '火灾自动报警系统': {
    question: '请测试火灾自动报警系统的探测器报警和控制器响应功能',
    steps: ['在消防控制室查看控制器面板：确认无故障灯/屏蔽灯常亮','抽查2个感烟探测器：使用专用烟感测试器加烟','观察控制器：30秒内收到报警信号，显示正确地址编码和部位','按下1个手动报警按钮','观察控制器：3秒内收到信号，启动声光报警器和应急广播','检查控制器主备电切换：断开主电源，备电应自动投入'],
    passCriteria: '探测器30s内报警、地址正确、手报3s内响应、主备电切换正常',
    video: '',
  },
  '自动喷水灭火系统': {
    question: '请测试自动喷水灭火系统末端试水装置',
    steps: ['找到系统最不利点的末端试水装置','打开末端试水阀','观察压力表读数：应≥0.05MPa','观察水流指示器：应动作并反馈信号至控制室','等待5分钟内压力开关动作并直接启动喷淋泵','到控制室确认：收到水流指示器、压力开关、喷淋泵启动信号','关闭试水阀，系统恢复'],
    passCriteria: '压力≥0.05MPa、水流指示器动作、压力开关启泵、控制室信号齐全',
    video: '',
  },
  '防排烟系统': {
    question: '请测试防排烟风机的启动和联动功能',
    steps: ['在消防控制室远程手动启动排烟风机→确认风机运转、收到反馈','现场手动启动送风机→确认运转方向正确','触发2个火灾探测器（联动测试）：风机自动启动','观察送风口/排烟口自动开启','排烟风机入口处的排烟防火阀：手动测试关闭→排烟风机应连锁停止','确认消防控制室显示所有风机、风口、防火阀状态'],
    passCriteria: '三种启动方式均正常、风口正确开启、防火阀连锁关闭有效',
    video: '',
  },
  '防火门': {
    question: '请检查防火门的闭门器、顺序器和联动关闭功能',
    steps: ['常闭防火门：手动开启后释放→应自动关闭严密','双扇防火门：开启后释放→顺序器控制关闭顺序正确','检查闭门器：无漏油、弹簧有效','测量门扇与门框缝隙：≥2mm不合格','常开防火门：触发火灾报警→应联动自动关闭','消防控制室：确认收到防火门关闭反馈信号'],
    passCriteria: '自闭严密、顺序正确、闭门器完好、常开门联动关闭有效',
    video: '',
  },
  '防火卷帘': {
    question: '请测试防火卷帘的手动和联动降落功能',
    steps: ['外观检查：帘板无锈蚀、导轨无卡阻、下方0.3m黄色警示线内无物品','操作两侧手动按钮：上升↓下降↓停止 均正常','操作手动速放链条：卷帘应能靠自重下降','疏散通道处：触发1个感烟探测器→卷帘降至距地1.8m','触发感温探测器→卷帘降到底','非疏散通道处：触发2个探测器→一步降到底','消防控制室：确认收到卷帘动作反馈信号'],
    passCriteria: '手动/联动升降正常、一步降/两步降正确、控制室反馈到位',
    video: '',
  },
  '灭火器配置': {
    question: '请检查灭火器的配置、压力和有效期',
    steps: ['抽查3个配置点的灭火器','查看压力表：指针必须在绿区','查看生产日期和维修标签：在有效期内（干粉5年、CO₂ 3年）','检查筒体：无锈蚀、变形','检查喷射软管和保险销：完好','核对灭火器类型是否与场所火灾类别匹配','核对配置数量是否符合GB 50140要求'],
    passCriteria: '压力绿区、有效期内、筒体完好、类型匹配、数量足够',
    video: '',
  },
  '消防应急照明和疏散指示标志': {
    question: '请测试应急照明灯的切换和持续时间',
    steps: ['抽查任一疏散路线上的3处应急照明灯','切断主电源→灯具应在5s内自动切换至应急状态','使用照度计测量地面最低水平照度：疏散走道≥1.0lx、人员密集场所≥3.0lx','记录应急照明持续时间→应≥90分钟','核查疏散指示标志的方向→应指向最近安全出口','确认标志安装高度和间距符合要求'],
    passCriteria: '5s内切换、照度达标、持续时间≥90分钟、方向正确',
    video: '',
  },
  '电气线路安全': {
    question: '请检查电气线路的敷设和保护措施',
    steps: ['查看吊顶内、墙体内的电气线路敷设方式','有可燃物的吊顶/墙体：线路应穿金属导管或封闭金属槽盒保护','查看电热设备：靠近可燃物时应有隔热散热措施','检查是否设有电气火灾监控系统（按规范需要时）','检查配电箱：箱门完好、无裸露导线、接地线完好'],
    passCriteria: '穿管保护到位、隔热措施完善、配电箱完好、接地可靠',
    video: '',
  },
  '消防电梯': {
    question: '请测试消防电梯的迫降和运行功能',
    steps: ['现场检查消防电梯前室面积和防火分隔','触发火灾报警→消防电梯应自动迫降至首层','检查消防电梯轿厢内：应设消防电话分机','手动操作消防电梯：从首层到顶层运行时间≤60s','测试消防电梯的消防员操作功能','消防控制室：确认显示消防电梯运行状态'],
    passCriteria: '自动迫降有效、运行时间≤60s、消防电话可用、设防水措施',
    video: '',
  },
  '消防控制室值班': {
    question: '请测试消防控制室值班人员的设备操作能力',
    steps: ['确认值班人员持证上岗、每班≥2人','要求值班员操作火灾报警控制器：消音→查看信息→复位','要求值班员使用消防电话总机呼叫水泵房分机','要求值班员启动应急广播进行全楼广播','查看值班记录：完整、至少保存1年','确认控制器处于自动状态（非手动）'],
    passCriteria: '持证上岗、双人值班、操作熟练、记录完整、控制器自动状态',
    video: '',
  },
  '消防水泵接合器': {
    question: '请检查消防水泵接合器的状态和标识',
    steps: ['现场查看水泵接合器外观完整性','检查是否被埋压、圈占、遮挡','查看永久性标志铭牌：标明供水系统类型和供水范围','确认距建筑外墙边缘≥5m','检查接口密封盖完好'],
    passCriteria: '无埋压遮挡、标识清晰、距外墙≥5m、接口完好',
    video: '',
  },
  '消防供电': {
    question: '请测试消防供电和备用电源切换功能',
    steps: ['确认消防用电设备采用专用供电回路','在消防控制室断开主电源→备用电源应自动投入','记录切换时间：≤15s','检查柴油发电机房（如有）：储油量≤1m³、防火分隔完好','测试发电机自启动：市电中断后15s内启动、30s内供电','检查配电柜：双电源转换开关（ATS）正常'],
    passCriteria: '专用回路、备电自动投入、切换≤15s、发电机正常启动',
    video: '',
  },
	  '消火栓': { question: '请测试消火栓的操作、水压和启泵功能', steps: ['打开消火栓箱门（开启角度≥160°）','检查箱内器材齐全','逆时针全开栓阀放水','充实水柱一般≥10m/高层≥13m','按下启泵按钮→30s内水泵启动','最不利点静压: 多层≥0.07MPa/高层≥0.15MPa'], passCriteria: '器材齐全、水压达标、启泵有效' },
	  '火灾报警': { question: '请测试火灾报警系统各组件', steps: ['控制器: 无故障灯/屏蔽灯、主备电切换正常','感烟探测器: 加烟→30s内报警→地址一致','感温探测器: 加温→响应时间合格','手动报警按钮: 按下→3s内信号至控制器','声光报警器: 声压级≥75dB、闪光清晰','联动控制: 断电/迫降/卷帘动作正确'], passCriteria: '30s报警、3s响应、地址正确' },
	  '消防电话': { question: '请测试消防电话系统', steps: ['核查关键部位均有消防电话分机','控制室总机逐一呼叫各分机','通话清晰无杂音','线路采用独立回路'], passCriteria: '分机到位、通话清晰、线路独立' },
	  '消防广播': { question: '请测试消防应急广播', steps: ['扬声器覆盖: 走道/大厅均有、间距≤25m','强制切换: 音量最小→火警→自动最大音量播放','分区广播: 按楼层/防火分区选择','全楼广播: 可同时播放疏散指令'], passCriteria: '覆盖到位、强制切换正常' },
	  '防火门': { question: '请检查防火门功能', steps: ['核查耐火等级(甲/乙/丙)','检查闭门器: 开启后自动关闭严密','双扇门顺序器关闭顺序正确','常开防火门: 触发火警→联动自动关闭','控制室确认收到关闭反馈'], passCriteria: '自闭严密、顺序正确、联动有效' },
	  '防火卷帘': { question: '请测试防火卷帘功能', steps: ['外观: 帘板无锈蚀、导轨无卡阻','按钮操作: 上升/下降/停止正常','手动速放链条顺畅','疏散通道: 两步降落','非疏散通道: 一步到底'], passCriteria: '手动/联动正常、降落正确' },
	  '自动喷水': { question: '请测试自动喷水灭火系统', steps: ['喷头: 无涂料/粉尘覆盖','报警阀组: 阀门启闭正常、水力警铃完好','末端试水: 压力≥0.05MPa','5分钟内压力开关动作→启泵','水流指示器动作→控制室信号'], passCriteria: '喷头完好、末端压力≥0.05MPa、启泵正常' },
	  '防排烟': { question: '请测试防排烟系统', steps: ['三种方式启动风机(远程/现场/联动)','送风口/排烟口自动开启','排烟防火阀280℃自动关闭并连锁停风机','自然排烟窗开启灵活'], passCriteria: '三种启动正常、风口/防火阀动作正确' },
	  '疏散': { question: '请检查疏散设施', steps: ['走道畅通、宽度≥1.1m','安全出口数量≥2个、向外开启','疏散指示间距≤20m','地面照度走道≥1.0lx/密集场所≥3.0lx'], passCriteria: '畅通、宽度达标、指示清晰、照度合格' },
	  '安全出口': { question: '请检查安全出口', steps: ['数量: 公共建筑≥2个','开启方向: 向疏散方向','门外1.4m无台阶','无锁闭/堵塞/遮挡','上方安全出口标志灯完好'], passCriteria: '数量足够、畅通无阻、标志完好' },
	  '消防水泵': { question: '请检查消防水泵接合器', steps: ['外观完好、无埋压/圈占/遮挡','标志铭牌清晰','距外墙≥5m','接口密封盖完好'], passCriteria: '无埋压遮挡、标识清晰' },
	  '防烟分区': { question: '请检查防烟分区', steps: ['每个分区≤500m²、不跨越防火分区','挡烟垂壁完好有效','底部距地面≥2.0m'], passCriteria: '分区合理、挡烟垂壁完好' },
	  '消火栓': { question: '请测试消火栓的操作、水压和启泵功能', steps: ['打开消火栓箱门（开启角度≥160°）','检查箱内器材齐全','逆时针全开栓阀放水','充实水柱一般≥10m/高层≥13m','按下启泵按钮→30s内水泵启动','最不利点静压: 多层≥0.07MPa/高层≥0.15MPa'], passCriteria: '器材齐全、水压达标、启泵有效' },
	  '火灾报警': { question: '请测试火灾报警系统各组件', steps: ['控制器: 无故障灯/屏蔽灯、主备电切换正常','感烟探测器: 加烟→30s内报警→地址一致','感温探测器: 加温→响应时间合格','手动报警按钮: 按下→3s内信号至控制器','声光报警器: 声压级≥75dB、闪光清晰','联动控制: 断电/迫降/卷帘动作正确'], passCriteria: '30s报警、3s响应、地址正确' },
	  '消防电话': { question: '请测试消防电话系统', steps: ['核查关键部位均有消防电话分机','控制室总机逐一呼叫各分机','通话清晰无杂音','线路采用独立回路'], passCriteria: '分机到位、通话清晰、线路独立' },
	  '消防广播': { question: '请测试消防应急广播', steps: ['扬声器覆盖: 走道/大厅均有、间距≤25m','强制切换: 音量最小→火警→自动最大音量播放','分区广播: 按楼层/防火分区选择','全楼广播: 可同时播放疏散指令'], passCriteria: '覆盖到位、强制切换正常' },
	  '防火门': { question: '请检查防火门功能', steps: ['核查耐火等级(甲/乙/丙)','检查闭门器: 开启后自动关闭严密','双扇门顺序器关闭顺序正确','常开防火门: 触发火警→联动自动关闭','控制室确认收到关闭反馈'], passCriteria: '自闭严密、顺序正确、联动有效' },
	  '防火卷帘': { question: '请测试防火卷帘功能', steps: ['外观: 帘板无锈蚀、导轨无卡阻','按钮操作: 上升/下降/停止正常','手动速放链条顺畅','疏散通道: 两步降落','非疏散通道: 一步到底'], passCriteria: '手动/联动正常、降落正确' },
	  '自动喷水': { question: '请测试自动喷水灭火系统', steps: ['喷头: 无涂料/粉尘覆盖','报警阀组: 阀门启闭正常、水力警铃完好','末端试水: 压力≥0.05MPa','5分钟内压力开关动作→启泵','水流指示器动作→控制室信号'], passCriteria: '喷头完好、末端压力≥0.05MPa、启泵正常' },
	  '防排烟': { question: '请测试防排烟系统', steps: ['三种方式启动风机(远程/现场/联动)','送风口/排烟口自动开启','排烟防火阀280℃自动关闭并连锁停风机','自然排烟窗开启灵活'], passCriteria: '三种启动正常、风口/防火阀动作正确' },
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

function getOperationGuide(facility) {
  for (const [k, v] of Object.entries(OPERATION_GUIDES)) {
    if (facility && facility.includes(k)) return v;
  }
  return null;
}

createApp({
  data() {
    return {
      page: 'home',
      inspectType: 'preopen',  // preopen | daily
      mode: 'first',
      scenes: SCENES,
      searchVenue: '',
      searched: false,
      historyList: [],
      // 检查状态
      inspectionId: '',
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
      recognition: null,
      // 规模参数 + 子类型
      showScaleInput: false,
      showSubTypePicker: false,
      scaleForm: { area: '', staff: '', floors: '', buildings: '1' },
      selectedSubType: '',
      pendingScene: null,
      samplingInfo: null,
      selectedBrand: '',
      showQaAnswer: false,
      showOpGuide: false,
      // 计算器 + 智能诊断
      showCalc: false,
      calcType: '',
      calcResult: null,
      calcInput: {},
      showDiagnosis: false,
      diagnosis: null,
      ownerRpt: null,
      showJumpMenu: false,
      sectionIndex: {},
      nineSmallSubTypes: ['小商店','小旅馆','小学校/幼儿园','小医院/诊所','小网吧','小餐饮场所','小歌舞娱乐场所','小美容洗浴场所','小生产加工企业','小培训机构','小民政服务机构','小托育机构','小健身场所','小娱乐休闲场所','小冰雪活动场所','小仓储物流场所','小民宿','小汽修场所','小照相馆','小金融服务场所','小网络直播场所','小公共体育场馆','小宗教活动场所'],
    };
  },

  computed: {
    progressPct() {
      if (!this.totalItems) return 0;
      return Math.min(100, Math.round((this.judgedCount / this.totalItems) * 100));
    },
  },

  methods: {
    categoryLabel(cat) {
      return { '消防管理': '管理', '技术条件': '技术', '设施完好': '设施' }[cat] || cat;
    },
    getRiskColor(h) {
      if (!h.fail_count) return 'green';
      if (h.important_fail_count >= 3) return 'red';
      if (h.important_fail_count >= 1) return 'orange';
      return 'yellow';
    },
    getTypicalHazard(facility) {
      return getTypicalHazard(facility);
    },
    getOperationGuide(facility) {
      return getOperationGuide(facility);
    },

    // === 导航 ===
    async goToItem(index) {
      if (index < 0 || index >= this.totalItems) return;
      try {
        const r = await API.get(`/${this.inspectionId}/item/${index}`);
        this.currentItem = r.data.data;
        this.currentIndex = index;
        // Section header — only show when section changes
        const step = this.currentItem.step || 5;
        const order = this.currentItem.section_order || 0;
        const secName = this.getSectionName(step, order) || '';
        if (secName !== this._lastSectionName) {
          this.currentSectionName = secName;
          this.currentStepName = this.currentItem.step_name || '';
          this._lastSectionName = secName;
        } else {
          this.currentSectionName = '';
          this.currentStepName = '';
        }
        this.showQaAnswer = false;
        this.selectedBrand = '';
        this.showOpGuide = false;
      } catch (e) { console.error(e); }
    },
    async goPrev() { if (this.currentIndex > 0) await this.goToItem(this.currentIndex - 1); },
    async goNext() { if (this.currentIndex < this.totalItems - 1) await this.goToItem(this.currentIndex + 1); },

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
      if (scene.key === 'nine_small') this.showSubTypePicker = true;
      else this.showSubTypePicker = false;
      this.showScaleInput = true;
      this.selectedSubType = '';
      this.scaleForm = { area: '', staff: '', floors: '', buildings: '1' };
    },
    async confirmStartInspection() {
      const s = this.scaleForm;
      const scene = this.pendingScene;
      const params = {
        venue_type: scene.key,
        inspection_type: this.inspectType,
        location: '',
        inspector: '消防员',
        staff_count: parseInt(s.staff) || 0,
        floor_count: parseInt(s.floors) || 0,
        area_sqm: parseInt(s.area) || 0,
        building_count: parseInt(s.buildings) || 1,
        sub_type: this.selectedSubType,
      };
      try {
        const r = await API.post('/start', params);
        const d = r.data.data;
        this.inspectionId = d.inspection_id;
        this.totalItems = d.total_items;
        this.currentIndex = 0;
        this.inspected = false;
        this.failCount = 0;
        this.judgedCount = 0;
        this.judgments = {};
        this.samplingInfo = { staff: d.staff_sample, floor: d.floor_sample };
        this.showScaleInput = false;
        this.showSubTypePicker = false;
        this.page = 'inspect';
        await this.goToItem(0);
      } catch (e) { alert('启动检查失败: ' + e.message); }
    },

    async startRecheck(history) {
      try {
        const r = await API.post('/recheck', { previous_inspection_id: history.inspection_id, inspector: '消防员' });
        const d = r.data.data;
        this.inspectionId = d.inspection_id;
        this.totalItems = d.total_items;
        this.currentIndex = 0;
        this.inspected = false;
        this.failCount = 0;
        this.judgedCount = 0;
        this.judgments = {};
        this.page = 'inspect';
        await this.goToItem(0);
      } catch (e) { alert('启动复查失败: ' + e.message); }
    },

    // === 提交判断（可覆盖之前的结果） ===
    // 获取项目的系统分组键（用于跳过同类子项）
    getSystemGroup(item) {
      const f = item?.facility || '';
      if (f.includes('消火栓')) return '消火栓系统';
      if (f.includes('报警') || f.includes('探测器') || f.includes('声光') || f.includes('手动报警')) return '火灾自动报警';
      if (f.includes('喷水') || f.includes('喷头') || f.includes('报警阀') || f.includes('末端试水') || f.includes('水流指示器')) return '自动喷水';
      if (f.includes('排烟') || f.includes('防烟') || f.includes('防火阀') || f.includes('送风')) return '防排烟';
      if (f.includes('防火门') || f.includes('闭门器') || f.includes('顺序器') || f.includes('耐火')) return '防火门';
      if (f.includes('防火卷帘')) return '防火卷帘';
      if (f.includes('广播') || f.includes('扬声器')) return '消防广播';
      if (f.includes('消防电话')) return '消防电话';
      if (f.includes('气体灭火') || f.includes('储瓶') || f.includes('防护区')) return '气体灭火';
      if (f.includes('泡沫')) return '泡沫灭火';
      if (f.includes('发电机') || f.includes('储油') || f.includes('供电')) return '消防供电';
      if (f.includes('灭火器')) return '灭火器';
      if (f.includes('应急照明') || f.includes('疏散指示')) return '应急照明';
      if (f.includes('消防电梯')) return '消防电梯';
      return f;
    },

    async judge(result) {
      const wasJudged = this.judgments[this.currentIndex] !== undefined;
      const wasFail = wasJudged && this.judgments[this.currentIndex].result === 'fail';
      const wasNA = wasJudged && this.judgments[this.currentIndex].result === 'na';

      let note = '';
      if (result === 'fail') {
        note = prompt('请填写问题描述:', this.judgments[this.currentIndex]?.note || '') || '';
        this.diagnosis = this.getDiagnosis(this.currentItem);
        this.showDiagnosis = true;
      } else if (result === 'na') {
        note = '不涉及';
        this.showDiagnosis = false;
        this.diagnosis = null;

        // 跳过同类系统的所有子项（用 /next 端点，每次自动推进）
        const currentGroup = this.getSystemGroup(this.currentItem);
        let skipped = 0;
        while (true) {
          try {
            const r = await API.get(`/${this.inspectionId}/next`);
            const nextItem = r.data.data;
            if (!nextItem || r.data.is_complete) break;
            const nextGroup = this.getSystemGroup(nextItem);
            if (nextGroup !== currentGroup) {
              // Different system → stop here, load this item
              this.currentItem = nextItem;
              this.currentIndex = skipped + this.currentIndex + 1;
              this.showQaAnswer = false;
              this.selectedBrand = '';
              this.showOpGuide = false;
              break;
            }
            // Same system → auto-judge and continue
            this.judgments[this.currentIndex + skipped + 1] = { result: 'na', note: '自动跳过' };
            API.post(`/${this.inspectionId}/judge`, { item_index: this.currentIndex + skipped + 1, result: 'na', note: '自动跳过', judge_source: 'manual' }).catch(()=>{});
            skipped++;
          } catch(e) { break; }
        }
        this.judgedCount += skipped + (wasJudged ? 0 : 1);
        this.judgments[this.currentIndex] = { result, note };
        if (skipped === 0) {
          // No skipping happened (already at last item or error), just load next
          try {
            const r = await API.get(`/${this.inspectionId}/item/${this.currentIndex + 1}`);
            this.currentItem = r.data.data;
            this.currentIndex++;
          } catch(e) {}
        }
        return;
      } else {
        this.showDiagnosis = false;
        this.diagnosis = null;
      }

      try {
        await API.post(`/${this.inspectionId}/judge`, { item_index: this.currentIndex, result, note, judge_source: 'manual' });
      } catch (e) { console.error(e); }

      // 更新本地记录
      if (!wasJudged) this.judgedCount++;
      if (wasFail && result !== 'fail') this.failCount = Math.max(0, this.failCount - 1);
      if (!wasFail && result === 'fail') this.failCount++;
      if (wasNA && result !== 'na' && !wasFail) this.failCount = Math.max(0, this.failCount);
      // N/A items don't count as fail

      this.judgments[this.currentIndex] = { result, note };

      // 自动跳到下一项
      if (this.currentIndex < this.totalItems - 1) {
        await this.goToItem(this.currentIndex + 1);
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
    async toggleJumpMenu() {
      this.showJumpMenu = !this.showJumpMenu;
      if (this.showJumpMenu) await this.buildSectionIndex();
    },
    judgedInRange(start, end) {
      let c = 0;
      for (let i = start; i <= end; i++) { if (this.judgments[i]) c++; }
      return c;
    },
    async buildSectionIndex() {
      if (Object.keys(this.sectionIndex).length > 0) return;
      const idx = {};
      let lastSection = ''; let sectionStart = 0;
      // Fetch every item to accurately detect section boundaries
      const batchSize = 5;
      for (let pos = 0; pos < this.totalItems; pos += batchSize) {
        try {
          const promises = [];
          for (let i = pos; i < Math.min(pos + batchSize, this.totalItems); i++) {
            promises.push(API.get(`/${this.inspectionId}/item/${i}`));
          }
          const results = await Promise.all(promises);
          for (let j = 0; j < results.length; j++) {
            const actualPos = pos + j;
            const item = results[j].data.data || {};
            const step = item.step || 5;
            const order = item.section_order || 0;
            const secName = this.getSectionName(step, order);
            if (secName && secName !== lastSection && actualPos > 0) {
              if (lastSection) idx[lastSection] = { start: sectionStart, end: actualPos - 1 };
              sectionStart = actualPos;
            }
            if (secName) lastSection = secName;
          }
        } catch(e) { break; }
      }
      if (lastSection) idx[lastSection] = { start: sectionStart, end: this.totalItems - 1 };
      this.sectionIndex = idx;
    },
    getSectionName(step, order) {
      if (this.inspectType === 'daily') {
        const dm = {31:'3.1 建筑消防合法性',32:'3.2 消防安全管理',33:'3.3 消防设施器材',34:'3.4 建筑防火与疏散',35:'3.5 消防产品检查',36:'3.6 电器线路燃气管路',37:'3.7 火灾隐患整改'};
        return dm[step] || '';
      }
      const o = order || 0;
      if (o >= 800) return '附、特殊附加';
      if (o >= 720) return '二十二、声音视频警报';
      if (o >= 710) return '二十一、消防控制室';
      if (o >= 700) return '二十、消防电梯';
      if (o >= 690) return '十九、燃气设施';
      if (o >= 680) return '十八、电气线路';
      if (o >= 670) return '十七、灭火器';
      if (o >= 660) return '十六、应急照明疏散指示';
      if (o >= 650) return '十五、防火门';
      if (o >= 640) return '十四、防火卷帘';
      if (o >= 630) return '十三、防排烟设施';
      if (o >= 620) return '十二、气体灭火';
      if (o >= 610) return '十一、水泵接合器';
      if (o >= 600) return '十、消防水源及室外消火栓';
      if (o >= 590) return '九、自动喷水灭火';
      if (o >= 580) return '八、室内消火栓';
      if (o >= 570) return '七、火灾自动报警';
      if (o >= 560) return '六、安全疏散';
      if (o >= 550) return '五、防火分区及分隔';
      if (o >= 540) return '四、平面布置';
      if (o >= 530) return '三、总平面布局';
      if (o >= 520) return '二、消防安全管理';
      if (o >= 510) return '一、消防安全责任';
      if (o >= 490) return '法律依据';
      return '';
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

    // === 拍照 ===
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
      } catch (e) {
        this.photoResult = { violation: null, reason: '分析失败: ' + e.message, confidence: 0 };
      }
      this.photoAnalyzing = false;
    },

    confirmPhotoResult() {
      this.judge(this.photoResult?.violation ? 'fail' : 'pass');
      this.showPhoto = false;
      this.photoResult = null;
    },

    // === 报告 ===
    async viewReport() {
      try {
        const r = await API.get(`/${this.inspectionId}/report`);
        this.report = r.data.data;
        this.page = 'report';
      } catch (e) { alert('获取报告失败: ' + e.message); }
    },

    newInspection() {
      this.page = 'home';
      this.report = null;
      this.ownerRpt = null;
    },

    // === 业主告知书 ===
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
      win.document.write(`<html><head><meta charset="UTF-8"><title>消防安全隐患整改告知书</title>
<style>body{font-family:SimSun,serif;max-width:700px;margin:20px auto;font-size:14px;line-height:1.8}
h3{text-align:center;font-size:20px}.or-meta{display:flex;gap:20px;margin:12px 0}
.or-score{padding:10px;border-radius:4px;margin:10px 0;font-weight:bold}
.risk-red{background:#fff1f0;color:#cf1322}.risk-orange{background:#fff7e6;color:#d46b08}
.risk-yellow{background:#fffbe6;color:#d48806}.risk-green{background:#f6ffed;color:#389e0d}
.or-section{margin:16px 0}.or-section h4{font-size:16px;margin-bottom:8px}
.or-item{padding:8px 12px;margin:6px 0;border-radius:4px}
.urgent{border-left:4px solid #d4380d;background:#fff1f0}
.deadline{border-left:4px solid #e85d04;background:#fff7e6}
.suggestion{border-left:4px solid #faad14;background:#fffbe6}
.or-note{color:#666;font-size:13px}.or-src{color:#1890ff;font-size:12px}
.or-footer{padding:12px;background:#fafafa;border-radius:6px;margin:16px 0}
.or-sign{display:flex;gap:30px;margin-top:30px;padding-top:20px;border-top:1px dashed #ccc}
@media print{body{margin:0;padding:10px}button{display:none}}
</style></head><body>${el.innerHTML}</body></html>`);
      win.document.close();
      setTimeout(() => win.print(), 500);
    },
    printReport() {
      window.print();
    },

    // === 法规检索 + 语音 ===
    startSearch() {
      this.page = 'search';
      this.searchResult = '';
      this.searchQuery = '';
    },
    async doSearch() {
      const q = this.searchQuery.trim();
      if (!q) return;
      this.searching = true;
      this.searchResult = '';
      try {
        const chatAPI = axios.create({ baseURL: API_BASE.replace('/inspection', '/agent') });
        const r = await chatAPI.post('/chat', { message: q, scene: 'general' });
        this.searchResult = r.data.reply || r.data.answer || '未获取到结果';
      } catch (e) {
        this.searchResult = '查询失败: ' + (e.response?.data?.detail || e.message);
      }
      this.searching = false;
    },

    // === 语音转文字（MediaRecorder + 服务端 faster-whisper） ===
    voiceAvailable() {
      // 检测 MediaRecorder + getUserMedia 支持（远好于 Web Speech API）
      const hasMedia = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
      const hasRecorder = typeof MediaRecorder !== 'undefined';
      const isSecure = location.protocol === 'https:' || location.hostname === 'localhost';
      return hasMedia && hasRecorder && isSecure;
    },
    voiceUnavailableReason() {
      if (typeof MediaRecorder === 'undefined') {
        const ua = navigator.userAgent;
        if (/iPad|iPhone|iPod/.test(ua)) return 'iOS 请使用 Safari 浏览器（iOS 14.5+）';
        if (/MicroMessenger/.test(ua)) return '微信内置浏览器不支持录音，请点击右上角"在浏览器中打开"';
        return '您的浏览器不支持录音功能，请使用 Chrome/Safari 浏览器';
      }
      if (location.protocol !== 'https:' && location.hostname !== 'localhost') {
        return '录音功能需要 HTTPS 安全连接';
      }
      return '';
    },
    async startVoice() {
      // 手动停止录音
      if (this.isRecording) {
        this.stopVoice();
        return;
      }

      // 不可用时给出具体原因
      if (!this.voiceAvailable()) {
        const reason = this.voiceUnavailableReason();
        this.searchResult = '⚠️ ' + reason;
        return;
      }

      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        this._mediaStream = stream;

        // 检测支持的 MIME 类型（移动端通常支持 webm 或 mp4）
        const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
          ? 'audio/webm;codecs=opus'
          : MediaRecorder.isTypeSupported('audio/mp4')
            ? 'audio/mp4'
            : 'audio/webm';

        const recorder = new MediaRecorder(stream, { mimeType });
        const chunks = [];

        recorder.ondataavailable = (e) => {
          if (e.data.size > 0) chunks.push(e.data);
        };

        recorder.onstart = () => {
          this.isRecording = true;
          this.searchResult = '';
          this.searchQuery = '🎤 正在聆听...';
          console.log('[Voice] MediaRecorder 已启动, mimeType:', mimeType);
        };

        recorder.onstop = async () => {
          console.log('[Voice] 录音结束, chunks:', chunks.length);
          this.isRecording = false;
          this.searchQuery = '';

          // 释放麦克风
          stream.getTracks().forEach(t => t.stop());

          if (chunks.length === 0) {
            this.searchResult = '⚠️ 未录制到音频，请重试';
            return;
          }

          const blob = new Blob(chunks, { type: mimeType });
          console.log('[Voice] 音频大小:', (blob.size / 1024).toFixed(1), 'KB');

          // 上传到服务端转文字
          this.searching = true;
          this.searchResult = '🎧 AI 正在聆听...';
          try {
            const form = new FormData();
            form.append('file', blob, 'recording.' + (mimeType.includes('mp4') ? 'mp4' : 'webm'));
            const speechAPI = axios.create({ baseURL: API_BASE.replace('/inspection', '/speech') });
            const r = await speechAPI.post('/transcribe', form);
            const text = r.data?.text || r.data?.transcript || '';
            console.log('[Voice] 识别结果:', text);
            if (text.trim()) {
              this.searchQuery = text.trim();
              this.doSearch();
            } else {
              this.searchResult = '⚠️ 未识别到语音内容，请重试或使用文字输入';
              this.searching = false;
            }
          } catch (e) {
            console.error('[Voice] 上传失败:', e);
            this.searchResult = '⚠️ 语音识别失败: ' + (e.response?.data?.detail || e.message || '网络错误');
            this.searching = false;
          }
        };

        this._recorder = recorder;
        recorder.start();
        console.log('[Voice] 开始录音...');
      } catch (e) {
        console.error('[Voice] getUserMedia 失败:', e);
        this.isRecording = false;
        if (e.name === 'NotAllowedError') {
          const isAndroid = /Android/.test(navigator.userAgent);
          const msg = isAndroid
            ? '麦克风权限未开启\n\n请在 Chrome 地址栏右侧点击🔒图标 → 权限 → 麦克风 → 允许\n\n或: 手机设置 → 应用管理 → Chrome → 权限 → 麦克风 → 允许'
            : '麦克风权限未开启\n\n请允许浏览器访问麦克风后重试\n\n（iOS: 设置 → Safari → 麦克风）';
          alert(msg);
        } else if (e.name === 'NotFoundError') {
          alert('未找到麦克风设备，请检查设备连接');
        } else {
          alert('无法访问麦克风: ' + (e.message || '未知错误'));
        }
      }
    },
    stopVoice() {
      if (this._recorder && this._recorder.state === 'recording') {
        this._recorder.stop();
      }
      if (this._mediaStream) {
        this._mediaStream.getTracks().forEach(t => t.stop());
      }
      this.isRecording = false;
    },
  },
}).mount('#app');
