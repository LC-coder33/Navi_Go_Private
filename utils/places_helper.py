import requests
from typing import List, Dict, Optional
import sys
import os
import math
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import GOOGLE_CLOUD_API_KEY

# Places API 타입으로 매핑
THEME_TO_PLACE_TYPE = {
    "박물관": ["museum"],
    "미술관": ["art_gallery"],
    "문화/역사": ["church", "hindu_temple", "mosque", "synagogue", "palace", "historic_site", "archaeological_site", "monument"],
    "관광명소": ["tourist_attraction", "point_of_interest", "landmark", "city_hall", "courthouse", "embassy", "town_square"],
    "자연/아웃도어": ["park", "natural_feature", "campground", "beach", "rv_park", "picnic_ground", "waterfall", "pier", "marina"],
    "음식/맛집": ["restaurant", "cafe", "bar", "bakery", "meal_takeaway", "meal_delivery", "ice_cream_shop", "night_club"],
    "쇼핑": ["shopping_mall", "department_store", "market", "jewelry_store", "shoe_store", "clothing_store", "book_store", "electronics_store", "convenience_store", "supermarket"],
    "휴양/힐링": ["spa", "beauty_salon", "amusement_park", "zoo", "hot_spring", "hair_care", "massage", "gym"]
}

def get_nearby_places(location: Dict[str, float], selected_themes: List[str], 
                     radius: int = 5000) -> List[Dict]:
    """
    선택된 위치 주변의 관광지를 검색합니다.
    
    Args:
        location (Dict[str, float]): 위도/경도 좌표
        selected_themes (List[str]): 선택된 여행 테마 리스트
        radius (int): 검색 반경 (미터)
    
    Returns:
        List[Dict]: 검색된 장소 목록
    """
    # 선택된 테마에 해당하는 place type들을 모두 가져옴
    place_types = []
    for theme in selected_themes:
        place_types.extend(THEME_TO_PLACE_TYPE.get(theme, []))
    
    all_places = []
    
    for place_type in place_types:
        base_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        params = {
            "location": f"{location['lat']},{location['lng']}",
            "radius": radius,
            "type": place_type,
            "language": "ko",
            "key": GOOGLE_CLOUD_API_KEY
        }
        
        try:
            response = requests.get(base_url, params=params)
            response.raise_for_status()
            results = response.json().get("results", [])
            
            # 중복 제거를 위해 place_id를 키로 사용
            for place in results:
                place_details = {
                    "place_id": place["place_id"],
                    "name": place["name"],
                    "location": place["geometry"]["location"],
                    "rating": place.get("rating", 0),
                    "user_ratings_total": place.get("user_ratings_total", 0),
                    "types": place["types"],
                    "place_type": place_type  # 원본 검색 타입 저장
                }
                
                # 사진 참조 ID가 있는 경우 추가
                if "photos" in place:
                    place_details["photo_reference"] = place["photos"][0]["photo_reference"]
                
                # 가격 수준이 있는 경우 추가 (1~4, 낮은 것부터)
                if "price_level" in place:
                    place_details["price_level"] = place["price_level"]
                
                all_places.append(place_details)
                
        except Exception as e:
            print(f"Error fetching places for type {place_type}: {str(e)}")
            continue
    
    # 중복 제거
    unique_places = {place["place_id"]: place for place in all_places}
    
    def calculate_score(place):
        rating = place.get("rating", 0)
        reviews = place.get("user_ratings_total", 0)
        
        # 필터링 조건 강화 (리뷰 100개 미만 & 평점 4.0 미만 제외)
        if reviews < 100 or rating < 4.0:
            return -1  # 제외 대상
        
        # 리뷰 수 가중치 계산 (0~1 정규화)
        max_reviews = 5000  # 최대 리뷰 수 기준
        review_weight = min(reviews / max_reviews, 1.0)
        
        # 평점 가중치 (5점 만점 기준)
        rating_weight = rating / 5
        
        # 최종 점수 (리뷰 수 60%, 평점 40% 가중치)
        score = (review_weight * 0.6 + rating_weight * 0.4) * 100
        
        return round(score, 1)

    # 중복 제거
    unique_places = {place["place_id"]: place for place in all_places}

    # 필터링 적용
    filtered_places = []
    for place in unique_places.values():
        if calculate_score(place) != -1:
            filtered_places.append(place)

    # 점수 기준 정렬
    sorted_places = sorted(
        filtered_places,
        key=lambda x: calculate_score(x),
        reverse=True
    )

    return sorted_places[:50]  # 상위 50개만 반환

def get_place_details(place_id: str) -> Optional[Dict]:
    """
    특정 장소의 상세 정보를 가져옵니다.
    
    Args:
        place_id (str): Google Places place_id
    
    Returns:
        Optional[Dict]: 장소 상세 정보
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
        
        # 필요한 정보만 추출하여 반환
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
    
    Args:
        photo_reference (str): 사진 참조 ID
        max_width (int): 최대 이미지 너비
    
    Returns:
        Optional[str]: 사진 URL
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