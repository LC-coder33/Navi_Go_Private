from googleapiclient.discovery import build
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import config0

class DetailedDestinationAnalyzer:
    def __init__(self, api_key):
        self.youtube = build('youtube', 'v3', developerKey=api_key)
        
    def analyze_destination(self, place_info, max_results=30):
        """특정 여행지 관련 영상 분석"""
        videos = []
        
        # 한달 전 날짜 계산
        last_month = datetime.now() - timedelta(days=30)
        last_month_str = last_month.strftime('%Y-%m-%dT%H:%M:%SZ')
        
        # 검색 쿼리 최적화 (구체적인 장소명 + 도시명으로 검색)
        search_query = f"{place_info['specific_place']} {place_info['city']} 여행"
        
        try:
            request = self.youtube.search().list(
                part='snippet',
                q=search_query,
                type='video',
                order='relevance',
                publishedAfter=last_month_str,
                maxResults=max_results,
                regionCode='KR',
                relevanceLanguage='ko'
            )
            response = request.execute()
            
            # 비디오 상세 정보 수집
            video_ids = [item['id']['videoId'] for item in response['items']]
            video_stats = self.get_videos_stats(video_ids)
            
            for item, stats in zip(response['items'], video_stats):
                # 제목이나 설명에 장소명이 포함된 영상만 필터링
                if (place_info['specific_place'] in item['snippet']['title'].lower() or
                    place_info['specific_place'] in item['snippet']['description'].lower()):
                    video_data = {
                        'specific_place': place_info['specific_place'],
                        'city': place_info['city'],
                        'category': place_info['category'],
                        'title': item['snippet']['title'],
                        'description': item['snippet']['description'],
                        'published_at': item['snippet']['publishedAt'],
                        'view_count': stats['view_count'],
                        'like_count': stats['like_count'],
                        'comment_count': stats.get('comment_count', 0),
                        'channel_title': item['snippet']['channelTitle']
                    }
                    videos.append(video_data)
                    
        except Exception as e:
            print(f"Error analyzing {place_info['specific_place']}: {str(e)}")
            
        return pd.DataFrame(videos)
    
    def get_videos_stats(self, video_ids):
        """비디오 통계 수집"""
        stats = []
        try:
            request = self.youtube.videos().list(
                part='statistics',
                id=','.join(video_ids)
            )
            response = request.execute()
            
            for item in response['items']:
                video_stats = {
                    'view_count': int(item['statistics'].get('viewCount', 0)),
                    'like_count': int(item['statistics'].get('likeCount', 0)),
                    'comment_count': int(item['statistics'].get('commentCount', 0))
                }
                stats.append(video_stats)
        except Exception as e:
            print(f"Error getting video stats: {str(e)}")
            
        return stats
    
    def calculate_trend_score(self, df):
        """트렌드 점수 계산"""
        if df.empty:
            return df
            
        # 시간 처리
        df['published_at'] = pd.to_datetime(df['published_at']).dt.tz_localize(None)
        now = pd.Timestamp.now().tz_localize(None)
        
        # 최근성 점수 (최근 일수록 높은 점수)
        df['days_ago'] = (now - df['published_at']).dt.total_seconds() / (24 * 60 * 60)
        df['recency_score'] = 1 - (df['days_ago'] / 30).clip(0, 1)
        
        # 조회수 점수
        df['view_score'] = np.log1p(df['view_count']) / np.log1p(df['view_count'].max())
        
        # 참여도 점수 (좋아요 + 댓글)
        df['engagement_rate'] = (df['like_count'] + df['comment_count']) / df['view_count'].clip(1)
        df['engagement_score'] = (df['engagement_rate'] - df['engagement_rate'].min()) / \
                               (df['engagement_rate'].max() - df['engagement_rate'].min()).clip(1e-10)
        
        # 종합 점수 계산 (가중치 조정 가능)
        df['trend_score'] = (
            df['recency_score'] * 0.35 +     # 최근성
            df['view_score'] * 0.35 +        # 조회수
            df['engagement_score'] * 0.30     # 참여도
        )
        
        return df

def main():
    API_KEY = config0.YOUTUBE_DATA
    analyzer = DetailedDestinationAnalyzer(API_KEY)
    
    # 구체적인 여행지 정보 정의
    destinations = [
        # 강릉
        {'specific_place': '정동진시간박물관', 'city': '강릉', 'category': '문화/박물관'},
        {'specific_place': '안목커피거리', 'city': '강릉', 'category': '카페거리'},
        {'specific_place': '주문진수산시장', 'city': '강릉', 'category': '전통시장'},
        {'specific_place': '경포대해변', 'city': '강릉', 'category': '해변'},
        
        # 부산
        {'specific_place': '광안리해수욕장', 'city': '부산', 'category': '해변'},
        {'specific_place': '송정해수욕장', 'city': '부산', 'category': '해변'},
        {'specific_place': '감천문화마을', 'city': '부산', 'category': '문화마을'},
        {'specific_place': '영도대교', 'city': '부산', 'category': '랜드마크'},
        {'specific_place': '해운대블루라인파크', 'city': '부산', 'category': '액티비티'},
        
        # 제주
        {'specific_place': '비자림', 'city': '제주', 'category': '자연'},
        {'specific_place': '함덕해수욕장', 'city': '제주', 'category': '해변'},
        {'specific_place': '카페더콘테나', 'city': '제주', 'category': '카페'},
        {'specific_place': '천지연폭포', 'city': '제주', 'category': '자연'},
        {'specific_place': '우도', 'city': '제주', 'category': '섬'},
        
        # 전주
        {'specific_place': '경기전', 'city': '전주', 'category': '문화유적'},
        {'specific_place': '한옥레일바이크', 'city': '전주', 'category': '액티비티'},
        {'specific_place': '동문예술거리', 'city': '전주', 'category': '문화거리'}
    ]
    
    all_videos = pd.DataFrame()
    
    # 각 여행지별 분석
    for place_info in destinations:
        print(f"\n{place_info['city']} - {place_info['specific_place']} 분석 중...")
        videos_df = analyzer.analyze_destination(place_info)
        if not videos_df.empty:
            videos_df = analyzer.calculate_trend_score(videos_df)
            all_videos = pd.concat([all_videos, videos_df])
    
    if all_videos.empty:
        print("분석할 데이터가 없습니다.")
        return
        
    # 장소별 종합 분석
    place_trends = all_videos.groupby(['city', 'specific_place', 'category']).agg({
        'trend_score': 'mean',
        'view_count': ['mean', 'sum'],
        'title': 'count'
    }).round(4)
    
    place_trends.columns = ['트렌드 점수', '평균 조회수', '총 조회수', '영상 수']
    place_trends = place_trends.sort_values('트렌드 점수', ascending=False)
    
    print("\n=== 인기 여행지 트렌드 순위 ===")
    pd.set_option('display.max_rows', None)
    pd.set_option('display.max_columns', None)
    print(place_trends)
    
    # 상위 5개 여행지의 인기 영상
    print("\n=== Top 5 여행지의 대표 인기 영상 ===")
    top_places = place_trends.head().index
    for city, place, category in top_places:
        place_videos = all_videos[
            (all_videos['city'] == city) & 
            (all_videos['specific_place'] == place)
        ].sort_values('view_count', ascending=False)
        
        print(f"\n{city} - {place} ({category}):")
        for _, video in place_videos.head(2).iterrows():
            print(f"- {video['title']}")
            print(f"  조회수: {video['view_count']:,}, 좋아요: {video['like_count']:,}")
            print(f"  채널: {video['channel_title']}")
    
    # 도시별 인기 카테고리 분석
    city_category_trends = all_videos.groupby(['city', 'category'])['trend_score'].mean().unstack()
    print("\n=== 도시별 인기 카테고리 ===")
    print(city_category_trends.round(4))
    
    # 결과 저장
    place_trends.to_csv('trending_specific_places.csv', encoding='utf-8-sig')
    print("\n분석 결과가 'trending_specific_places.csv'에 저장되었습니다.")

if __name__ == "__main__":
    main()