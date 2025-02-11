from typing import List, Dict, Optional
import logging
import requests
from config import GOOGLE_CLOUD_API_KEY

class HotelsHelper:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def _calculate_relevance_score(self, hotel_data: Dict) -> float:
        """
        호텔의 관련성 점수를 계산합니다.
        
        고려하는 요소:
        - 리뷰 수 (가장 높은 가중치)
        - 평점
        - 거리
        - 가격 수준
        """
        score = 0.0
        
        # 리뷰 수 점수 (최대 50점)
        review_count = int(hotel_data.get('user_ratings_total', 0))
        review_score = min(50, (review_count / 20))  # 1000개 리뷰 → 50점
        score += review_score
        
        # 평점 점수 (최대 30점, 리뷰 수와 연계)
        try:
            rating = float(hotel_data.get('rating', 0))
            # 리뷰 수에 따른 신뢰도 가중치 (0.2 ~ 1.0)
            review_weight = min(1.0, max(0.2, review_count / 1000))
            rating_score = (rating * 6) * review_weight  # 5점 만점 → 최대 30점
            score += rating_score
        except (ValueError, TypeError):
            pass

        # 거리 점수 (최대 15점)
        try:
            # distance는 미터 단위로 제공됨
            distance_km = float(hotel_data.get('distance', 0)) / 1000
            distance_score = max(0, 15 - (distance_km * 0.75))  # 거리 1km당 0.75점 감소
            score += distance_score
        except (ValueError, TypeError):
            pass

        # 가격 수준 점수 (최대 5점)
        # price_level은 0~4 사이의 값 (0: 무료, 4: 매우 비쌈)
        try:
            price_level = int(hotel_data.get('price_level', 2))
            # 중간 가격대(2)일 때 최고점
            price_score = 5 - abs(2 - price_level) * 1.5
            score += max(0, price_score)
        except (ValueError, TypeError):
            pass

        return score

    def _get_hotel_details(self, place_id: str) -> Optional[Dict]:
        """
        특정 호텔의 상세 정보를 가져옵니다.
        """
        try:
            details_url = "https://maps.googleapis.com/maps/api/place/details/json"
            details_params = {
                "place_id": place_id,
                "fields": "name,rating,formatted_address,geometry,photos,price_level," \
                         "user_ratings_total,reviews,website,url,formatted_phone_number," \
                         "opening_hours,price_level",
                "key": GOOGLE_CLOUD_API_KEY,
                "language": "ko"  # 한국어로 결과 요청
            }
            
            response = requests.get(details_url, params=details_params)
            data = response.json()
            
            if data.get("status") == "OK" and "result" in data:
                return data["result"]
            return None
            
        except Exception as e:
            self.logger.error(f"Error fetching hotel details: {str(e)}")
            return None

    def search_hotels(self, location: Dict[str, float], radius: int = 5000) -> List[Dict]:
        """
        주어진 위치의 호텔 정보를 검색합니다.
        
        Args:
            location: {'lat': float, 'lng': float} 형태의 위치 정보
            radius: 검색 반경 (미터 단위, 기본값 5km)
        """
        try:
            # 먼저 주변 호텔 검색
            search_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
            search_params = {
                "location": f"{location['lat']},{location['lng']}",
                "radius": radius,
                "type": "lodging",  # 숙박시설 검색
                "key": GOOGLE_CLOUD_API_KEY
            }
            
            hotels = []
            next_page_token = None
            
            # 최대 2페이지까지만 검색 (페이지당 20개, 총 40개)
            for _ in range(2):
                if next_page_token:
                    search_params["pagetoken"] = next_page_token
                
                response = requests.get(search_url, params=search_params)
                data = response.json()
                
                if data.get("status") != "OK":
                    break
                
                for place in data.get("results", []):
                    # 기본 필터링: 최소 리뷰 수와 평점 조건
                    if (place.get("user_ratings_total", 0) < 50 or 
                        place.get("rating", 0) < 3.5):
                        continue
                    
                    # 호텔 상세 정보 가져오기
                    details = self._get_hotel_details(place["place_id"])
                    if not details:
                        continue
                    
                    hotel_info = {
                        'place_id': place["place_id"],
                        'name': details.get("name", ""),
                        'rating': details.get("rating", 0),
                        'review_count': details.get("user_ratings_total", 0),
                        'reviews': details.get("reviews", [])[:3],  # 최근 리뷰 3개
                        'address': details.get("formatted_address", ""),
                        'phone': details.get("formatted_phone_number", ""),
                        'website': details.get("website", ""),
                        'maps_url': details.get("url", ""),
                        'price_level': details.get("price_level", 0),
                        'photos': details.get("photos", [])[:5],  # 최대 5장의 사진
                        'location': {
                            'lat': details["geometry"]["location"]["lat"],
                            'lng': details["geometry"]["location"]["lng"]
                        },
                        'distance': place.get("distance", 0),  # 미터 단위
                        'opening_hours': details.get("opening_hours", {}).get("weekday_text", [])
                    }
                    
                    # relevance score 계산
                    hotel_info['relevance_score'] = self._calculate_relevance_score(place)
                    
                    hotels.append(hotel_info)
                
                next_page_token = data.get("next_page_token")
                if not next_page_token:
                    break

            # 정렬: relevance score 기준
            hotels.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)

            # 상위 10개 호텔 반환
            return hotels[:10]

        except Exception as e:
            self.logger.error(f"Error searching hotels: {str(e)}")
            return []

    def get_hotel_photo(self, photo_reference: str, max_width: int = 800) -> Optional[str]:
        """
        호텔 사진 URL을 가져옵니다.
        """
        try:
            photo_url = "https://maps.googleapis.com/maps/api/place/photo"
            params = {
                "maxwidth": max_width,
                "photo_reference": photo_reference,
                "key": GOOGLE_CLOUD_API_KEY
            }
            
            response = requests.get(photo_url, params=params)
            if response.status_code == 200:
                return response.url
            return None
            
        except Exception as e:
            self.logger.error(f"Error fetching hotel photo: {str(e)}")
            return None