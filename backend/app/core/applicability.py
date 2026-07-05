"""Auto-detect system applicability based on venue scale parameters"""
# Return dict of system_name -> bool (True = applicable, False = N/A)
def check_applicability(venue_type, area_sqm, floor_count, building_count):
    is_highrise = floor_count >= 10  # GB 50016: >=10 floors or height >33m
    is_large = area_sqm > 1500
    is_very_large = area_sqm > 3000
    is_very_tall = floor_count >= 18

    public_gathering = venue_type in ('hotel','mall','entertainment','restaurant')
    has_beds = venue_type in ('hospital','elderly')
    is_industrial = venue_type in ('factory')

    return {
        # 室内消火栓: 高度>15m或体积>5000m³
        'indoor_hydrant': floor_count >= 2 or area_sqm > 500,

        # 火灾自动报警: 一类高层/面积>1500/设机械排烟等
        'fire_alarm': is_highrise or is_large or public_gathering or has_beds,

        # 自动喷水: 一类高层/面积>1500/>100床位医院
        'sprinkler': is_highrise or is_very_large or (has_beds and area_sqm > 3000),

        # 防排烟: 高度>50m或内走道>20m无可开启窗
        'smoke_control': is_very_tall or (is_highrise and is_large),

        # 消防电梯: 高度>33m (>=10层)
        'fire_elevator': is_highrise,

        # 消防供电分级: 一类高层→一级, 二类高层→二级, 其他→三级
        'fire_power_level1': is_very_tall,  # 一级负荷
        'fire_power_level2': is_highrise and not is_very_tall,  # 二级负荷
        'generator': is_very_tall or venue_type == 'hospital',  # 发电机

        # 气体灭火: 大型数据中心/贵重设备用房
        'gas_extinguish': venue_type in ('hospital','factory','highrise') and is_large,

        # 泡沫灭火: 工业/厂房
        'foam_extinguish': is_industrial and is_large,

        # 消防控制室: 有报警/喷淋系统就需要
        'control_room': is_highrise or is_large or public_gathering,
    }
