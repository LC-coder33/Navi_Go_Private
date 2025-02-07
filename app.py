import streamlit as st
import requests
from datetime import datetime, timedelta
import json
import sys
import os

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import GOOGLE_CLOUD_API_KEY
from utils.places_helper import get_nearby_places, get_place_details, get_place_photo

def initialize_session_state():
    if 'selected_place' not in st.session_state:
        st.session_state.selected_place = None
    if 'place_details' not in st.session_state:
        st.session_state.place_details = None

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

def get_place_details(place_id):
    """선택된 장소의 상세 정보를 가져옵니다."""
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
        return response.json().get("result", {})
    except Exception as e:
        st.error(f"장소 정보 조회 중 오류가 발생했습니다: {str(e)}")
        return None

def main():
    st.title("여행 계획 도우미 🌎")
    initialize_session_state()
    
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
                format_func=lambda x: descriptions[x],
                key="place_select"
            )
            
            if selected_index is not None:
                selected_place = suggestions[selected_index]
                if st.button("이 장소로 선택"):
                    place_details = get_place_details(selected_place["place_id"])
                    if place_details:
                        st.session_state.selected_place = selected_place
                        st.session_state.place_details = place_details
                        st.success(f"선택된 여행지: {selected_place['description']}")
    
    if st.session_state.selected_place:
        # 2. 여행 날짜 선택
        st.subheader("2. 여행 날짜를 선택해주세요")
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input(
                "출발일",
                min_value=datetime.now().date(),
                value=datetime.now().date() + timedelta(days=7)
            )
        with col2:
            end_date = st.date_input(
                "도착일",
                min_value=start_date,
                value=start_date + timedelta(days=2)
            )
        
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
        themes = ["문화/역사", "자연/아웃도어", "음식/맛집", "쇼핑", "휴양/힐링"]
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
                num_travelers = st.number_input(
                    "동행자 수",
                    min_value=2,
                    max_value=10,
                    value=2
                )
        
        # 계획 생성 버튼
                # 관광지 검색 버튼
        if st.button("주변 관광지 검색", type="primary"):
            if not selected_themes:
                st.warning("최소 하나의 여행 테마를 선택해주세요.")
                return
                
            with st.spinner("주변 관광지를 검색중입니다..."):
                # places_helper에서 관광지 검색
                location = st.session_state.place_details["geometry"]["location"]
                nearby_places = get_nearby_places(location, selected_themes)
                
                if nearby_places:
                    place_count = len(nearby_places)
                    
                    # 여행 기간과 발견된 장소 수를 비교
                    trip_days = (end_date - start_date).days + 1
                    places_per_day = place_count / trip_days
                    
                    if place_count < 3:
                        st.warning(f"""
                        🤔 {place_count}개의 관광지만 발견되었습니다.
                        
                        추천:
                        - 다른 여행지를 고려해보세요
                        - 다른 여행 테마를 선택해보세요
                        - 여행 기간을 줄여보세요 (현재 {trip_days}일)
                        """)
                    elif places_per_day < 2:
                        st.warning(f"""
                        ⚠️ {trip_days}일 동안 방문하기에는 관광지가 다소 부족할 수 있습니다.
                        발견된 관광지: {place_count}개
                        
                        추천:
                        - 여행 기간을 줄여보세요
                        - 다른 테마나 주변 지역도 고려해보세요
                        """)
                    else:
                        st.success(f"✨ {place_count}개의 관광지를 찾았습니다!")
                    
                    # 관광지 목록 표시
                    for place in nearby_places:
                        with st.expander(f"🏷️ {place['name']} ({place.get('rating', 'N/A')}⭐)"):
                            col1, col2 = st.columns([2, 1])
                            
                            with col1:
                                if "photo_reference" in place:
                                    photo_url = get_place_photo(place["photo_reference"])
                                    if photo_url:
                                        st.image(photo_url, width=300)
                                
                                # 가격 수준 표시
                                price_level = place.get("price_level", 0)
                                st.write(f"가격 수준: {'💰' * price_level if price_level else 'N/A'}")
                                
                                # 상세 정보 버튼
                                if st.button(f"상세 정보 보기##{place['place_id']}", key=place['place_id']):
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
                                
                            with col2:
                                st.write(f"유형: {place['place_type']}")
                                st.write(f"평가: {place.get('user_ratings_total', 0)}개")
                else:
                    st.warning("검색된 관광지가 없습니다. 다른 테마를 선택해보세요.")

if __name__ == "__main__":
    main()