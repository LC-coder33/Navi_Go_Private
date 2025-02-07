import os
import json
import gradio as gr
import pandas as pd
from datetime import datetime, timedelta
import requests
from typing import Dict, List, Tuple
import config0

class TravelTrendAnalyzer:
    def __init__(self):
        self.naver_trend_url = config0.TREND_REQUEST_URL
        self.naver_search_url = config0.CAFE_REQUEST_URL
        self.trend_headers = {
            "X-Naver-Client-Id": config0.NAVER_TREND_CLIENT_ID,
            "X-Naver-Client-Secret": config0.NAVER_TREND_CLIENT_SECRET,
            "Content-Type": "application/json"
        }
        self.search_headers = {
            "X-Naver-Client-Id": config0.NAVER_CAFE_CLIENT_ID,
            "X-Naver-Client-Secret": config0.NAVER_CAFE_CLIENT_SECRET
        }
        # Tour API 지역 코드
        self.area_codes = {
            '서울': '1', '인천': '2', '대전': '3', '대구': '4',
            '광주': '5', '부산': '6', '울산': '7', '세종': '8',
            '경기': '31', '강원': '32', '충북': '33', '충남': '34',
            '경북': '35', '경남': '36', '전북': '37', '전남': '38', '제주': '39'
        }
        # 시도명 매핑 (네이버 주소 형식 → Tour API 형식)
        self.sido_mapping = {
            '서울특별시': '서울', '인천광역시': '인천', '대전광역시': '대전',
            '대구광역시': '대구', '광주광역시': '광주', '부산광역시': '부산',
            '울산광역시': '울산', '세종특별자치시': '세종', '경기도': '경기',
            '강원도': '강원', '충청북도': '충북', '충청남도': '충남',
            '경상북도': '경북', '경상남도': '경남', '전라북도': '전북',
            '전라남도': '전남', '제주특별자치도': '제주'
        }

    def get_location_details(self, location: str) -> Dict:
        """네이버 검색 API로 장소 상세 정보 획득"""
        try:
            response = requests.get(
                f"{self.naver_search_url}/local",
                headers=self.search_headers,
                params={"query": location, "display": 5}
            )
            
            if response.status_code == 200:
                items = response.json().get('items', [])
                if items:
                    item = items[0]  # 첫 번째 결과 사용
                    # 주소에서 시도 추출
                    address = item.get('address', '')
                    sido = address.split(' ')[0]
                    # Tour API 형식으로 변환
                    normalized_sido = self.sido_mapping.get(sido)
                    area_code = self.area_codes.get(normalized_sido) if normalized_sido else None
                    
                    return {
                        "title": item.get('title', '').replace('<b>', '').replace('</b>', ''),
                        "address": address,
                        "area_code": area_code,
                        "image": item.get('image', ''),
                        "link": item.get('link', '')
                    }
            return None
        except Exception as e:
            print(f"Error getting location details: {str(e)}")
            return None

    def get_trend_data(self, keywords: List[str], start_date: str, end_date: str, 
                      age: str = None, gender: str = None) -> pd.DataFrame:
        """네이버 데이터랩 API로 트렌드 데이터 수집"""
        keyword_chunks = [keywords[i:i + 5] for i in range(0, len(keywords), 5)]
        all_results = []
        
        for chunk in keyword_chunks:
            body = {
                "startDate": start_date,
                "endDate": end_date,
                "timeUnit": "date",
                "keywordGroups": [
                    {
                        "groupName": k,
                        "keywords": [k],
                        "category": ""
                    } for k in chunk
                ]
            }
            
            if age:
                body["ages"] = [age]
            if gender:
                body["gender"] = gender
                
            try:
                response = requests.post(
                    self.naver_trend_url,
                    headers=self.trend_headers,
                    json=body
                )
                
                if response.status_code == 200:
                    result = response.json()
                    df = self._process_trend_data(result)
                    if df is not None:
                        all_results.append(df)
                else:
                    print(f"Error {response.status_code}: {response.text}")
                    
            except Exception as e:
                print(f"Error making request: {str(e)}")
                continue
            
        if all_results:
            return pd.concat(all_results, ignore_index=True)
        return None

    def _process_trend_data(self, raw_data: Dict) -> pd.DataFrame:
        """트렌드 데이터 처리"""
        try:
            processed_data = []
            for result in raw_data.get('results', []):
                for item in result.get('data', []):
                    processed_data.append({
                        'location': result.get('title', ''),
                        'date': item.get('period', ''),
                        'value': item.get('ratio', 0)
                    })
            return pd.DataFrame(processed_data)
        except Exception as e:
            print(f"Error processing trend data: {str(e)}")
            return None

    def get_top_locations(self) -> Dict:
        """인기 여행지 정보 수집"""
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        # 주요 관광 키워드로 검색
        search_keywords = [
            "관광지", "여행지", "관광명소", "여행명소",
            "박물관", "미술관", "유적지", "문화재"
        ]
        
        results = {
            "current_hot": [],
            "age_based": {},
            "seasonal": {}
        }
        
        # 현재 인기 여행지
        trend_data = self.get_trend_data(search_keywords, start_date, end_date)
        if trend_data is not None:
            current_hot = trend_data.groupby('location')['value'].mean().nlargest(4)
            for loc in current_hot.index:
                details = self.get_location_details(loc)
                if details:
                    results["current_hot"].append({
                        "location": loc,
                        "trend_score": float(current_hot[loc]),
                        "details": details
                    })
        
        # 연령대별 인기 여행지
        age_groups = ['1', '2', '3', '4', '5', '6']  # 10대~60대
        for age in age_groups:
            trend_data = self.get_trend_data(search_keywords, start_date, end_date, age=age)
            if trend_data is not None:
                top_by_age = trend_data.groupby('location')['value'].mean().nlargest(2)
                results["age_based"][f"{age}0대"] = []
                for loc in top_by_age.index:
                    details = self.get_location_details(loc)
                    if details:
                        results["age_based"][f"{age}0대"].append({
                            "location": loc,
                            "trend_score": float(top_by_age[loc]),
                            "details": details
                        })
        
        # 계절별 인기 여행지
        seasons = {
            "봄": ("2024-03-01", "2024-05-31"),
            "여름": ("2024-06-01", "2024-08-31"),
            "가을": ("2024-09-01", "2024-11-30"),
            "겨울": ("2024-12-01", "2025-02-28")
        }
        
        for season, (start, end) in seasons.items():
            trend_data = self.get_trend_data(search_keywords, start, end)
            if trend_data is not None:
                top_by_season = trend_data.groupby('location')['value'].mean().nlargest(2)
                results["seasonal"][season] = []
                for loc in top_by_season.index:
                    details = self.get_location_details(loc)
                    if details:
                        results["seasonal"][season].append({
                            "location": loc,
                            "trend_score": float(top_by_season[loc]),
                            "details": details
                        })
        
        return results

def create_trend_ui():
    analyzer = TravelTrendAnalyzer()
    
    def update_trends():
        results = analyzer.get_top_locations()
        
        output_text = "🔥 현재 인기 여행지 TOP 4\n"
        for item in results["current_hot"]:
            details = item["details"]
            output_text += f"- {item['location']} (트렌드 점수: {item['trend_score']:.1f})\n"
            output_text += f"  위치: {details['address']}\n"
            output_text += f"  지역 코드: {details['area_code']}\n"
        
        output_text += "\n👥 연령대별 인기 여행지\n"
        for age, locations in results["age_based"].items():
            output_text += f"\n{age}:\n"
            for item in locations:
                details = item["details"]
                output_text += f"- {item['location']} (트렌드 점수: {item['trend_score']:.1f})\n"
                output_text += f"  위치: {details['address']}\n"
                output_text += f"  지역 코드: {details['area_code']}\n"
        
        output_text += "\n🌍 계절별 인기 여행지\n"
        for season, locations in results["seasonal"].items():
            output_text += f"\n{season}:\n"
            for item in locations:
                details = item["details"]
                output_text += f"- {item['location']} (트렌드 점수: {item['trend_score']:.1f})\n"
                output_text += f"  위치: {details['address']}\n"
                output_text += f"  지역 코드: {details['area_code']}\n"
        
        image_urls = [item["details"]["image"] for item in results["current_hot"] if item["details"]["image"]]
        return output_text, image_urls

    with gr.Blocks() as interface:
        gr.Markdown("# 여행 트렌드 분석")
        with gr.Row():
            refresh_btn = gr.Button("트렌드 새로고침")
        
        with gr.Row():
            output_text = gr.Textbox(label="트렌드 분석 결과")
        
        with gr.Row():
            image_gallery = gr.Gallery(label="인기 여행지 이미지")
        
        refresh_btn.click(
            fn=update_trends,
            outputs=[output_text, image_gallery]
        )
    
    return interface

if __name__ == "__main__":
    interface = create_trend_ui()
    interface.launch()