import os
import sys
import urllib.request
import config0
import matplotlib.pyplot as plt
import json
import pandas as pd

client_id = config0.NAVER_TREND
client_secret = config0.TREND_SECRET
url = config0.TREND_REQUEST_URL
body = "{\"startDate\":\"2024-01-01\",\"endDate\":\"2024-04-30\",\"timeUnit\":\"month\",\"keywordGroups\":[{\"groupName\":\"한글\",\"keywords\":[\"한글\",\"korean\"]},{\"groupName\":\"영어\",\"keywords\":[\"영어\",\"english\"]}],\"device\":\"pc\",\"ages\":[\"1\",\"2\",\"3\"],\"gender\":\"f\"}"

request = urllib.request.Request(url)
request.add_header("X-Naver-Client-Id", client_id)
request.add_header("X-Naver-Client-Secret", client_secret)
request.add_header("Content-Type", "application/json")
response = urllib.request.urlopen(request, data=body.encode("utf-8"))
rescode = response.getcode()
if(rescode==200):
    response_body = response.read()
    data = json.loads(response_body.decode('utf-8'))
    
    # JSON 데이터를 DataFrame으로 변환
    results = data['results']
    
    # 데이터 정리
    trends_data = []
    for result in results:
        group_name = result['title']
        for datum in result['data']:
            datum['group'] = group_name
            trends_data.append(datum)
    
    df = pd.DataFrame(trends_data)
    
    # 시각화
    plt.rcParams['font.family'] = 'Malgun Gothic'
    plt.figure(figsize=(12, 6))
    for group in df['group'].unique():
        group_data = df[df['group'] == group]
        plt.plot(group_data['period'], group_data['ratio'], label=group)
    
    plt.title('네이버 검색어 트렌드 분석 (2024.01-04)')
    plt.xlabel('기간')
    plt.ylabel('검색 비율')
    plt.legend()
    plt.xticks(rotation=45)
    plt.grid(True)
    plt.tight_layout()
    plt.show()
print(json.dumps(json.loads(response_body.decode('utf-8')), indent=2))