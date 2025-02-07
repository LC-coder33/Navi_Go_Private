import requests
import config0

def search_image(query):
    url = "https://dapi.kakao.com/v2/search/image"
    
    headers = {
        "Authorization": "KakaoAK " + config0.KAKAO_RESTAPI
    }
    
    # 검색 파라미터
    params = {
        "query": query,
        "size": 4
    }
    
    # API 요청
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        result = response.json()
        return result['documents']
    else:
        print(f"Error: {response.status_code}")
        return None

results = search_image("강촌레일파크")

# 결과 출력
if results:
    for idx, image in enumerate(results, 1):
        print(f"\n이미지 {idx}")
        print(f"이미지 URL: {image['image_url']}")
        print(f"썸네일 URL: {image['thumbnail_url']}")
        print(f"출처: {image['display_sitename']}")