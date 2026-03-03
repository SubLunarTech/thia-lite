import math
from datetime import datetime
from typing import Dict, Any, List

def calculate_square_of_9(price: float) -> Dict[str, float]:
    """
    Computes W.D. Gann's Square of 9 levels around a given price point.
    Returns the cardinal (cross) and ordinal (diagonal) integers on the spiral 
    that act as mathematical support and resistance levels.
    """
    if price <= 0:
        return {}

    # Root of the price
    root = math.sqrt(price)
    
    # Floor to the current 'ring' integer
    base_root = math.floor(root)
    # The square of 9 moves in 45-degree (or 0.125 root) increments (360/45 = 8 increments per ring)
    # We will compute the classic angles around the root:
    # 0, 45, 90, 135, 180, 225, 270, 315, 360

    levels = []
    # From -1 full ring (360 degrees back) to +1 full ring (360 degrees forward)
    # Step by 45 degrees (+0.25 to the root per 90 degrees)
    for increment in [
        -2.0, -1.75, -1.5, -1.25, -1.0, -0.75, -0.5, -0.25,
        0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0
    ]:
        angle = (increment * 180)  # Convert root increments back to nominal angle representation
        raw_val = (root + increment) ** 2
        
        # Name the angle
        if increment == 0:
            label = "Origin (0°)"
        elif increment < 0:
            label = f"Support ({int(abs(angle))}° Back)"
        else:
            label = f"Resistance ({int(abs(angle))}° Forward)"
            
        levels.append({
            "angle_from_origin": int(angle),
            "label": label,
            "price": round(raw_val, 4)
        })

    # Sort levels by price ascending
    levels = sorted(levels, key=lambda x: x["price"])
    
    return {
        "origin_price": price,
        "root": round(root, 4),
        "levels": levels
    }

def calculate_planetary_price(longitude: float, scale_factors: List[float] = None) -> List[Dict[str, float]]:
    """
    Converts a planetary longitude (0-360) directly into potential Gann support/resistance prices.
    Uses scale factors (e.g., longitude * 10, longitude / 10) to map to realistic ticker prices.
    """
    if scale_factors is None:
        scale_factors = [0.1, 1.0, 10.0, 100.0]
        
    targets = []
    for scale in scale_factors:
        # Direct longitude price
        p_price = longitude * scale
        
        # Geocentric mirror (opposite sign)
        opposite_lon = (longitude + 180) % 360
        opp_price = opposite_lon * scale
        
        targets.append({
            "scale": scale,
            "direct_price": round(p_price, 4),
            "opposite_price": round(opp_price, 4),
        })
        
    return targets

def calculate_gann_angles(start_price: float, start_date_str: str, target_date_str: str, price_unit_per_day: float = 1.0) -> Dict[str, Any]:
    """
    Calculates Gann Angles spreading from an origin pivot (start_price/start_date) to a target date.
    Returns the expected price of each angle on the target_date.
    Angles: 
       1x1 (45 deg) = 1 unit price per 1 unit time
       1x2 (63.75)  = 1 unit price per 2 units time
       2x1 (26.25)  = 2 units price per 1 unit time
    """
    try:
        dt_start = datetime.strptime(start_date_str, "%Y-%m-%d")
        dt_target = datetime.strptime(target_date_str, "%Y-%m-%d")
        days_diff = (dt_target - dt_start).days
        
        if days_diff < 0:
            return {"error": "Target date must be after start date."}
            
        return {
            "origin_date": start_date_str,
            "target_date": target_date_str,
            "days_elapsed": days_diff,
            "origin_price": start_price,
            "price_unit": price_unit_per_day,
            "angles_up": {
                "1x1": round(start_price + (days_diff * price_unit_per_day), 4),      # 45 deg
                "1x2": round(start_price + ((days_diff / 2) * price_unit_per_day), 4), # 26.25 deg
                "2x1": round(start_price + ((days_diff * 2) * price_unit_per_day), 4), # 63.75 deg
                "1x4": round(start_price + ((days_diff / 4) * price_unit_per_day), 4),
                "4x1": round(start_price + ((days_diff * 4) * price_unit_per_day), 4),
            },
            "angles_down": {
                "1x1": round(start_price - (days_diff * price_unit_per_day), 4),
                "1x2": round(start_price - ((days_diff / 2) * price_unit_per_day), 4),
                "2x1": round(start_price - ((days_diff * 2) * price_unit_per_day), 4),
                "1x4": round(start_price - ((days_diff / 4) * price_unit_per_day), 4),
                "4x1": round(start_price - ((days_diff * 4) * price_unit_per_day), 4),
            }
        }
    except Exception as e:
        return {"error": str(e)}

def analyze_gann(price: float, planet_lons: Dict[str, float] = None, pivot_price: float = None, pivot_date: str = None, target_date: str = None) -> Dict[str, Any]:
    """A wrapper combining all Gann tools."""
    output = {
        "square_of_9": calculate_square_of_9(price)
    }
    
    if planet_lons:
        output["planetary_prices"] = {}
        for p_name, lon in planet_lons.items():
            output["planetary_prices"][p_name] = calculate_planetary_price(lon)
            
    if pivot_price and pivot_date and target_date:
        output["gann_angles"] = calculate_gann_angles(pivot_price, pivot_date, target_date)
        
    return output
