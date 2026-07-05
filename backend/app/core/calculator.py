"""Fire inspection calculators based on GB standards"""
import math

def calc_fire_zone(area, floors, has_sprinkler=True, is_highrise=False, is_underground=False):
    """防火分区数量计算 - GB 50016 Table 5.3.1"""
    if is_underground:
        max_per_zone = 500  # 地下设备用房可放宽到1000
        if has_sprinkler:
            max_per_zone = 1000
    elif is_highrise:
        max_per_zone = 1500  # 高层一二级
        if has_sprinkler:
            max_per_zone = 3000
    else:
        max_per_zone = 2500  # 单多层一二级
        if has_sprinkler:
            max_per_zone = 5000

    zones_per_floor = math.ceil(area / max_per_zone) if area > 0 else 1
    total_zones = zones_per_floor * max(floors, 1)

    return {
        'input': {'面积': f'{area}m²', '楼层': floors, '有自喷': has_sprinkler, '高层': is_highrise, '地下': is_underground},
        'standard': f'GB 50016-2014(2018) 表5.3.1: 每区≤{max_per_zone}m²',
        'result': f'每层{area}m² ÷ {max_per_zone}m²/区 = {zones_per_floor}个区 × {max(floors,1)}层 = {total_zones}个防火分区',
        'value': total_zones,
        'unit': '个',
    }

def calc_water_tank(area, floors, venue_type, has_sprinkler=True, is_highrise=False):
    """消防水池有效容积 - GB 50974"""
    # Simplified calculation
    # Outdoor hydrant: 15-40 L/s depending on building volume
    volume = area * max(floors, 1) * 3.5  # rough volume in m³
    if volume < 5000:
        outdoor_rate = 15  # L/s
    elif volume < 20000:
        outdoor_rate = 25
    elif volume < 50000:
        outdoor_rate = 30
    else:
        outdoor_rate = 40

    # Indoor hydrant: 10-40 L/s
    if is_highrise:
        indoor_rate = 20 if floors < 18 else 30
    else:
        indoor_rate = 10

    # Sprinkler: 15-30 L/s
    sprinkler_rate = 20 if has_sprinkler else 0

    # Duration
    if is_highrise:
        duration_h = 3  # 高层民用建筑
    elif venue_type in ('factory',):
        duration_h = 3
    else:
        duration_h = 2

    total_rate = outdoor_rate + indoor_rate + sprinkler_rate  # L/s
    total_volume = total_rate * duration_h * 3600 / 1000  # m³

    return {
        'input': {'面积': f'{area}m²', '楼层': floors, '场所': venue_type},
        'standard': f'GB 50974-2014: 室外{outdoor_rate}L/s + 室内{indoor_rate}L/s + 喷淋{sprinkler_rate}L/s × {duration_h}h',
        'result': f'({outdoor_rate}+{indoor_rate}+{sprinkler_rate})L/s × {duration_h}h × 3600s/h ÷ 1000 = {total_volume:.0f}m³',
        'value': round(total_volume),
        'unit': 'm³',
    }

def calc_evacuation(people_count, floor_num, is_highrise=False):
    """疏散宽度计算 - GB 50016 Table 5.5.21"""
    if is_highrise:
        indicator = 1.00  # m/百人
    elif floor_num >= 4:
        indicator = 1.00
    else:
        indicator = 0.65 if floor_num <= 2 else 0.75

    width = people_count * indicator / 100

    return {
        'input': {'人数': people_count, '楼层': floor_num, '高层': is_highrise},
        'standard': f'GB 50016-2014(2018) 表5.5.21: {indicator}m/百人',
        'result': f'{people_count}人 × {indicator}m/百人 ÷ 100 = {width:.2f}m',
        'value': round(width, 2),
        'unit': 'm',
    }

def calc_extinguisher(area, hazard_level='中危险级'):
    """灭火器配置数量 - GB 50140"""
    if hazard_level == '严重危险级':
        max_protection = 50  # m² per 3A extinguisher (A类)
        uf = 0.5  # unit factor
    elif hazard_level == '轻危险级':
        max_protection = 100
        uf = 1.0
    else:  # 中危险级
        max_protection = 75
        uf = 1.0

    K = 1.0  # 无消火栓和喷淋时; 0.7有消火栓; 0.5有喷淋; 0.3有消火栓和喷淋
    min_count = math.ceil(area * K * uf / max_protection)
    # At least 2 per location, and minimum spacing
    actual = max(min_count, 2)

    return {
        'input': {'面积': f'{area}m²', '危险等级': hazard_level},
        'standard': f'GB 50140-2005: {hazard_level}每具保护{max_protection}m², K={K}',
        'result': f'{area}m² × {K} ÷ {max_protection}m²/具 = {min_count}具 (最少2具)',
        'value': actual,
        'unit': '具',
    }
