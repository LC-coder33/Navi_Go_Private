import streamlit as st
import requests
from datetime import datetime, timedelta
import sys
import os
import pandas as pd

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import GOOGLE_CLOUD_API_KEY
from utils.places_helper import get_nearby_places, get_place_details, get_place_photo, THEME_TO_PLACE_TYPE
from utils.hotels_helper import HotelsHelper

def initialize_session_state():
    if 'selected_place' not in st.session_state:
        st.session_state.selected_place = None
    if 'place_details' not in st.session_state:
        st.session_state.place_details = None
    if 'selected_hotel' not in st.session_state:
        st.session_state.selected_hotel = None
    if 'travel_dates' not in st.session_state:
        st.session_state.travel_dates = None
    if 'distance_matrix' not in st.session_state:
        st.session_state.distance_matrix = None
    if 'daily_routes' not in st.session_state:
        st.session_state.daily_routes = None

def get_place_suggestions(query):
    """Google Places Autocomplete API를 호출하여 장소 추천을 받아옵니다."""
    if not query:
        return []
    
    base_url = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
    params = {
        "input": query,
        "types": "(regions)",  # 도시로 제한
        "language": "ko",     # 한글 결과
        "key": GOOGLE_CLOUD_API_KEY
    }
    
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        suggestions = response.json().get("predictions", [])
        return [{"description": place["description"], 
                "place_id": place["place_id"]} 
                for place in suggestions]
    except Exception as e:
        st.error(f"장소 검색 중 오류가 발생했습니다: {str(e)}")
        return []

def get_place_location(place_id):
    """선택된 장소의 위치 정보를 가져옵니다."""
    base_url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": "geometry,formatted_address,name",
        "language": "ko",
        "key": GOOGLE_CLOUD_API_KEY
    }
    
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        result = response.json().get("result", {})
        if result and "geometry" in result:
            return {
                "name": result.get("name"),
                "address": result.get("formatted_address"),
                "location": result["geometry"]["location"]
            }
    except Exception as e:
        st.error(f"장소 정보 조회 중 오류가 발생했습니다: {str(e)}")
    return None

def main():
    st.title("여행 계획 도우미 🌎")
    
    # 1. 여행지 선택
    st.subheader("1. 여행지를 선택해주세요")
    destination_query = st.text_input("여행지 검색", key="destination_search")
    
    if destination_query:
        suggestions = get_place_suggestions(destination_query)
        if suggestions:
            descriptions = [s["description"] for s in suggestions]
            selected_index = st.selectbox(
                "추천 장소 목록",
                range(len(descriptions)),
                format_func=lambda x: descriptions[x]
            )
            
            if selected_index is not None:
                selected_place = suggestions[selected_index]
                if st.button("이 장소로 선택"):
                    place_location = get_place_location(selected_place["place_id"])
                    if place_location:
                        st.session_state.selected_place = place_location
                        st.success(f"선택된 여행지: {place_location['name']}")
    
    if 'selected_place' in st.session_state:
        # 2. 여행 날짜 선택
        st.subheader("2. 여행 날짜를 선택해주세요")
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("출발일")
        with col2:
            # 출발일로부터 최대 14일까지만 선택 가능
            max_end_date = start_date + timedelta(days=14)
            end_date = st.date_input(
                "도착일",
                min_value=start_date,
                max_value=max_end_date,
                value=min(start_date + timedelta(days=2), max_end_date)
            )

        # 선택된 기간이 14일을 초과하는 경우 경고 메시지 표시
        duration = (end_date - start_date).days
        if duration > 14:
            st.warning("여행 기간은 최대 14일까지만 선택 가능합니다.")
        elif duration > 0:
            st.info(f"선택된 여행 기간: {duration}일")
        
        # 3. 예산 입력
        st.subheader("3. 예산을 입력해주세요")
        budget = st.number_input(
            "예산 (KRW)",
            min_value=0,
            value=1000000,
            step=100000,
            format="%d"
        )
        
        # 4. 여행 테마 선택
        st.subheader("4. 여행 테마를 선택해주세요")
        themes = list(THEME_TO_PLACE_TYPE.keys())
        selected_themes = st.multiselect(
            "관심있는 테마를 선택해주세요 (최대 3개)",
            themes,
            max_selections=3
        )
        
        # 5. 동행자 정보
        st.subheader("5. 동행자 정보를 입력해주세요")
        col1, col2 = st.columns(2)
        with col1:
            travel_with = st.selectbox(
                "여행 유형",
                ["혼자", "커플/부부", "가족", "친구", "단체"]
            )
        with col2:
            if travel_with != "혼자":
                num_travelers = st.number_input("동행자 수", min_value=2, max_value=10, value=2)
            else:
                num_travelers = 1
        
        # 6. 호텔 검색
        st.subheader("6. 주변 호텔 검색")
        if st.checkbox("호텔 검색하기"):
            with st.spinner("호텔을 검색중입니다..."):
                hotels_helper = HotelsHelper()
                hotels = hotels_helper.search_hotels(
                    location=st.session_state.selected_place["location"]
                )
            
            if hotels:
                st.success(f"🏨 {len(hotels)}개의 호텔을 찾았습니다!")
                
                # 정렬 옵션
                sort_option = st.selectbox(
                    "정렬 기준",
                    ["추천순", "리뷰 많은순", "평점 높은순", "거리순", "가격 낮은순"]
                )
                
                # 필터 옵션
                col1, col2, col3 = st.columns(3)
                with col1:
                    min_rating = st.slider("최소 평점", 3.5, 5.0, 3.5, 0.1)
                with col2:
                    min_reviews = st.slider("최소 리뷰 수", 0, 1000, 100, 50)
                with col3:
                    max_price_level = st.slider("최대 가격 수준", 1, 4, 4, 1)
                
                # 필터링
                filtered_hotels = [
                    h for h in hotels 
                    if float(h.get('rating', 0)) >= min_rating and 
                    int(h.get('review_count', 0)) >= min_reviews and
                    int(h.get('price_level', 0)) <= max_price_level
                ]
                
                # 정렬
                if sort_option == "리뷰 많은순":
                    filtered_hotels.sort(key=lambda x: int(x.get('review_count', 0)), reverse=True)
                elif sort_option == "평점 높은순":
                    filtered_hotels.sort(key=lambda x: float(x.get('rating', 0)), reverse=True)
                elif sort_option == "거리순":
                    filtered_hotels.sort(key=lambda x: float(x.get('distance', 0)))
                elif sort_option == "가격 낮은순":
                    filtered_hotels.sort(key=lambda x: int(x.get('price_level', 0)))
                else:  # 추천순
                    filtered_hotels.sort(key=lambda x: float(x.get('relevance_score', 0)), reverse=True)
                
                if not filtered_hotels:
                    st.warning("선택한 필터 조건에 맞는 호텔이 없습니다. 조건을 완화해보세요.")
                else:
                    # 호텔 목록 표시
                    for hotel in filtered_hotels[:5]:
                        with st.expander(f"🏨 {hotel['name']} ({hotel.get('rating', 'N/A')}⭐ • {hotel.get('review_count', 0)}개 리뷰)"):
                            col_left, col_right = st.columns([2, 1])
                            
                            with col_left:
                                # 호텔 사진
                                if hotel.get('photos'):
                                    photo_ref = hotel['photos'][0].get('photo_reference')
                                    if photo_ref:
                                        photo_url = hotels_helper.get_hotel_photo(photo_ref)
                                        if photo_url:
                                            st.image(photo_url, use_container_width=True)
                                
                                # 기본 정보
                                st.write(f"💰 가격 수준: {'💰' * hotel.get('price_level', 0)}")
                                st.markdown(f"""
                                📍 **주소**: {hotel.get('address', 'N/A')}  
                                📞 **전화**: {hotel.get('phone', 'N/A')}  
                                ⭐ **평점**: {hotel.get('rating', 'N/A')} / 5.0  
                                👥 **리뷰 수**: {hotel.get('review_count', 0)}개  
                                📏 **중심지로부터 거리**: {hotel.get('distance', 0)/1000:.1f}km  
                                """)
                                
                                # 영업시간
                                if hotel.get('opening_hours'):
                                    st.write("⏰ **영업시간:**")
                                    for hours in hotel['opening_hours']:
                                        st.write(hours)
                                
                                # 리뷰
                                if hotel.get('reviews'):
                                    st.write("💬 **최근 리뷰:**")
                                    for review in hotel['reviews']:
                                        st.markdown(f"""
                                        > ⭐ {review.get('rating', 'N/A')} - {review.get('text', '')}  
                                        > *{review.get('relative_time_description', '')}*
                                        ---
                                        """)
                                
                                # 링크
                                st.write("🔗 **바로가기:**")
                                cols = st.columns(2)
                                with cols[0]:
                                    if hotel.get('website'):
                                        st.markdown(f"[호텔 웹사이트]({hotel['website']})")
                                with cols[1]:
                                    if hotel.get('maps_url'):
                                        st.markdown(f"[Google Maps]({hotel['maps_url']})")
                            
                            with col_right:
                                # 지도
                                location = hotel.get('location', None)
                                if location:
                                    map_data = pd.DataFrame({
                                        'lat': [location['lat']],
                                        'lon': [location['lng']]
                                    })
                                    st.map(map_data)
            else:
                st.error("호텔을 찾을 수 없습니다. 다시 시도해주세요.")
                
        # 7. 음식점 검색 섹션 추가
        st.subheader("7. 주변 음식점 검색")
        if st.checkbox("음식점 검색하기"):
            with st.spinner("주변 음식점을 검색중입니다..."):
                # 음식/맛집 테마의 place type들만 사용
                food_places = get_nearby_places(
                    st.session_state.selected_place["location"], 
                    ["음식/맛집"]  # THEME_TO_PLACE_TYPE에서 음식/맛집 테마만 선택
                )
                
                if food_places:
                    st.success(f"🍽️ {len(food_places)}개의 음식점을 찾았습니다!")
                    
                    # 정렬 옵션
                    sort_option = st.selectbox(
                        "정렬 기준",
                        ["추천순", "리뷰 많은순", "평점 높은순"],
                        key="food_sort"
                    )
                    
                    # 필터 옵션
                    col1, col2 = st.columns(2)
                    with col1:
                        min_rating = st.slider("최소 평점", 3.5, 5.0, 3.5, 0.1, key="food_rating")
                    with col2:
                        min_reviews = st.slider("최소 리뷰 수", 0, 1000, 50, 50, key="food_reviews")
                    
                    # 필터링
                    filtered_places = [
                        p for p in food_places 
                        if float(p.get('rating', 0)) >= min_rating and 
                        int(p.get('user_ratings_total', 0)) >= min_reviews
                    ]
                    
                    # 정렬
                    if sort_option == "리뷰 많은순":
                        filtered_places.sort(key=lambda x: int(x.get('user_ratings_total', 0)), reverse=True)
                    elif sort_option == "평점 높은순":
                        filtered_places.sort(key=lambda x: float(x.get('rating', 0)), reverse=True)
                    
                    if not filtered_places:
                        st.warning("선택한 필터 조건에 맞는 음식점이 없습니다. 조건을 완화해보세요.")
                    else:
                        # 음식점 목록 표시
                        for place in filtered_places[:30]:  # 상위 30개만 표시
                            with st.expander(f"🍽️ {place['name']} ({place.get('rating', 'N/A')}⭐)"):
                                col1, col2 = st.columns([2, 1])
                                
                                with col1:
                                    # 음식점 사진
                                    if "photo_reference" in place:
                                        photo_url = get_place_photo(place["photo_reference"])
                                        if photo_url:
                                            st.image(photo_url, width=300)
                                    
                                    # 상세 정보 가져오기
                                    details = get_place_details(place['place_id'])
                                    if details:
                                        st.write("---")
                                        st.write(f"📍 주소: {details['address']}")
                                        if details.get('phone'):
                                            st.write(f"📞 전화번호: {details['phone']}")
                                        if details['opening_hours']:
                                            st.write("⏰ 영업시간:")
                                            for hours in details['opening_hours']:
                                                st.write(f"- {hours}")
                                        
                                        # 가격 수준
                                        price_level = details.get('price_level', None)
                                        if price_level:
                                            st.write(f"💰 가격 수준: {'💰' * price_level}")
                                        
                                        # 리뷰
                                        if details['reviews']:
                                            st.write("💬 추천 리뷰:")
                                            for review in details['reviews']:
                                                st.markdown(f"""
                                                > ⭐ {review['rating']} - {review['text']}  
                                                > *{review['time']}*
                                                ---
                                                """)
                                
                                with col2:
                                    st.write(f"⭐ 평점: {place.get('rating', 'N/A')} / 5.0")
                                    st.write(f"👥 리뷰 수: {place.get('user_ratings_total', 0)}개")
                                    if details and details.get('website'):
                                        st.markdown(f"🌐 [웹사이트]({details['website']})")
                else:
                    st.warning("검색된 음식점이 없습니다. 다시 시도해주세요.")
        
        # 8. 관광지 검색
        st.subheader("8. 주변 관광지 검색")
        if st.button("관광지 검색하기", type="primary"):
            if not selected_themes:
                st.warning("최소 하나의 여행 테마를 선택해주세요.")
                return
                
            with st.spinner("주변 관광지를 검색중입니다..."):
                nearby_places = get_nearby_places(
                    st.session_state.selected_place["location"], 
                    selected_themes
                )
                
                if nearby_places:
                    place_count = len(nearby_places)
                    st.success(f"✨ {place_count}개의 관광지를 찾았습니다!")
                    
                    for place in nearby_places:
                        with st.expander(f"🏷️ {place['name']} ({place.get('rating', 'N/A')}⭐)"):
                            col1, col2 = st.columns([2, 1])
                            
                            with col1:
                                if "photo_reference" in place:
                                    photo_url = get_place_photo(place["photo_reference"])
                                    if photo_url:
                                        st.image(photo_url, width=300)
                                details = get_place_details(place['place_id'])
                                if details:
                                    st.write("---")
                                    st.write(f"📍 주소: {details['address']}")
                                    if details['opening_hours']:
                                        st.write("⏰ 영업시간:")
                                        for hours in details['opening_hours']:
                                            st.write(hours)
                                    if details['reviews']:
                                        st.write("💬 리뷰:")
                                        for review in details['reviews']:
                                            st.write(f"- {review['text'][:100]}... ({review['rating']}⭐)")
                                price_level = place.get("price_level", None)
                                price_text = "💰" * price_level if price_level else "가격 수준 확인 불가"
                                st.write(f"가격 수준: {price_text}")
                            
                            with col2:
                                st.write(f"유형: {place['place_type']}")
                                st.write(f"평가: {place.get('user_ratings_total', 0)}개")
                                st.write(f"위도: {place['location']['lat']:.5f}")
                                st.write(f"경도: {place['location']['lng']:.5f}")
                else:
                    st.warning("검색된 관광지가 없습니다. 다른 테마를 선택해보세요.")
            
            

if __name__ == "__main__":
    main()