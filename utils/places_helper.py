import requests
from typing import List, Dict, Optional
import time
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import GOOGLE_CLOUD_API_KEY

# Places API 타입으로 매핑
THEME_TO_PLACE_TYPE = {
    "박물관": ["museum"],
    "미술관": ["art_gallery"],
    "문화/역사": ["church", "hindu_temple", "mosque", "synagogue", "palace", "historic_site", "archaeological_site"],
    "관광명소": ["tourist_attraction", "landmark", "city_hall", "courthouse", "embassy", "town_square"],
    "자연/아웃도어": ["park", "natural_feature", "campground", "beach", "rv_park", "picnic_ground", "waterfall", "pier", "marina"],
    "음식/맛집": ["restaurant", "cafe", "bar", "bakery", "meal_takeaway", "meal_delivery", "ice_cream_shop", "night_club"],
    "쇼핑": ["shopping_mall", "department_store", "market", "jewelry_store", "shoe_store", "clothing_store", "book_store", "electronics_store", "convenience_store", "supermarket"],
    "휴양/힐링": ["spa", "beauty_salon", "amusement_park", "zoo", "hot_spring", "hair_care", "massage", "gym"]
}

def calculate_city_radius(location: Dict[str, float]) -> int:
    """
    도시의 viewport 정보를 기반으로 적절한 검색 반경을 계산
    """
    base_url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "latlng": f"{location['lat']},{location['lng']}",
        "key": GOOGLE_CLOUD_API_KEY
    }
    
    try:
        response = requests.get(base_url, params=params)
        data = response.json()
        
        if data.get("results"):
            # 도시 정보를 찾기 위해 결과를 순회
            for result in data["results"]:
                if "locality" in result["types"]:
                    viewport = result["geometry"]["viewport"]
                    ne = viewport["northeast"]
                    sw = viewport["southwest"]
                    
                    # 위도/경도 차이를 km로 변환하여 대략적인 도시 크기 계산
                    lat_diff = abs(ne["lat"] - sw["lat"])
                    lng_diff = abs(ne["lng"] - sw["lng"])
                    
                    # 도시의 대각선 길이를 기준으로 반경 결정
                    city_size = (lat_diff ** 2 + lng_diff ** 2) ** 0.5
                    
                    if city_size > 0.5:  # 대도시 (예: 뉴욕, 도쿄)
                        return 50000
                    elif city_size > 0.2:  # 중간 크기 도시
                        return 30000
                    else:  # 작은 도시
                        return 15000
    except Exception as e:
        print(f"Error calculating city radius: {str(e)}")
    
    return 30000  # 기본값으로 30km 반환

def get_nearby_places(location: Dict[str, float], selected_themes: List[str]) -> List[Dict]:
    """
    선택된 위치 주변의 관광지를 검색합니다.
    동적 반경 조정과 결과 수에 따른 최적화를 포함합니다.
    """
    # 도시 크기에 따른 초기 검색 반경 계산
    initial_radius = calculate_city_radius(location)
    print(f"Initial search radius: {initial_radius}m")
    
    # 선택된 테마에 해당하는 place type들을 모두 가져옴
    place_types = []
    for theme in selected_themes:
        place_types.extend(THEME_TO_PLACE_TYPE.get(theme, []))
    
    all_places = []
    current_radius = initial_radius
    
    for place_type in place_types:
        results = []
        next_page_token = None
        
        while True:
            base_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
            params = {
                "location": f"{location['lat']},{location['lng']}",
                "radius": current_radius,
                "type": place_type,
                "language": "ko",
                "key": GOOGLE_CLOUD_API_KEY
            }
            
            if next_page_token:
                params["pagetoken"] = next_page_token
            
            try:
                response = requests.get(base_url, params=params)
                response.raise_for_status()
                data = response.json()
                
                # 결과 처리
                batch_results = data.get("results", [])
                results.extend(batch_results)
                
                # 다음 페이지 토큰 확인
                next_page_token = data.get("next_page_token")
                
                # 결과가 너무 많으면 반경 줄이기
                if len(results) >= 60 and not next_page_token:
                    current_radius = int(current_radius * 0.8)  # 40% 감소
                    print(f"Too many results, reducing radius to {current_radius}m")
                    results = results[:60]  # 최대 60개로 제한
                    break
                
                if not next_page_token:
                    break
                
                # API 제한을 위한 대기
                time.sleep(2)
                
            except Exception as e:
                print(f"Error fetching places for type {place_type}: {str(e)}")
                break
        
        # 결과 처리 및 중복 제거를 위한 정보 저장
        for place in results:
            place_details = {
                "place_id": place["place_id"],
                "name": place["name"],
                "location": place["geometry"]["location"],
                "rating": place.get("rating", 0),
                "user_ratings_total": place.get("user_ratings_total", 0),
                "types": place["types"],
                "place_type": place_type
            }
            
            if "photos" in place:
                place_details["photo_reference"] = place["photos"][0]["photo_reference"]
            
            if "price_level" in place:
                place_details["price_level"] = place["price_level"]
            
            all_places.append(place_details)
    
    # 중복 제거
    unique_places = {place["place_id"]: place for place in all_places}
    
    def calculate_score(place):
        rating = place.get("rating", 0)
        reviews = place.get("user_ratings_total", 0)
        
        if reviews < 100 or rating < 4.0:
            return -1
        
        max_reviews = 5000
        review_weight = min(reviews / max_reviews, 1.0)
        rating_weight = rating / 5
        
        score = (review_weight * 0.6 + rating_weight * 0.4) * 100
        return round(score, 1)
    
    # 필터링 및 정렬
    filtered_places = [place for place in unique_places.values() if calculate_score(place) != -1]
    sorted_places = sorted(filtered_places, key=calculate_score, reverse=True)
    
    return sorted_places[:50]  # 상위 50개만 반환

def get_place_details(place_id: str) -> Optional[Dict]:
    """
    특정 장소의 상세 정보를 가져옵니다.
    """
    base_url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": "name,formatted_address,geometry,opening_hours,rating,reviews,price_level,photos,website,formatted_phone_number",
        "language": "ko",
        "key": GOOGLE_CLOUD_API_KEY
    }
    
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        result = response.json().get("result", {})
        
        return {
            "name": result.get("name"),
            "address": result.get("formatted_address"),
            "location": result.get("geometry", {}).get("location"),
            "opening_hours": result.get("opening_hours", {}).get("weekday_text", []),
            "rating": result.get("rating"),
            "reviews": [
                {
                    "text": review.get("text"),
                    "rating": review.get("rating"),
                    "time": review.get("relative_time_description")
                }
                for review in result.get("reviews", [])
                if len(review.get("text", "")) > 30  # 30자 이상 리뷰만 필터링
                and review.get("rating", 0) >= 4     # 4점 이상 리뷰만 표시
            ][:3],  # 상위 3개 리뷰만
            "price_level": result.get("price_level"),
            "photos": [photo.get("photo_reference") for photo in result.get("photos", [])[:5]],  # 최대 5장
            "website": result.get("website"),
            "phone": result.get("formatted_phone_number")
        }
        
    except Exception as e:
        print(f"Error fetching place details: {str(e)}")
        return None

def get_place_photo(photo_reference: str, max_width: int = 400) -> Optional[str]:
    """
    장소 사진의 URL을 가져옵니다.
    """
    base_url = "https://maps.googleapis.com/maps/api/place/photo"
    params = {
        "photoreference": photo_reference,
        "maxwidth": max_width,
        "key": GOOGLE_CLOUD_API_KEY
    }
    
    try:
        response = requests.get(base_url, params=params, allow_redirects=False)
        if response.status_code == 302:  # Google은 리다이렉트로 실제 이미지 URL을 제공
            return response.headers["Location"]
    except Exception as e:
        print(f"Error fetching photo: {str(e)}")
    
    return None