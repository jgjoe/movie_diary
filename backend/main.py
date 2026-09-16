import os
import random
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import google.generativeai as genai
import requests
from pydantic import BaseModel

# 로깅 설정 (로그가 잘 보이도록 레벨과 포맷 설정)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# .env 파일 로드
load_dotenv()

app = FastAPI()

# --- CORS 설정 ---
origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "https://jgjoe.github.io",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API 키 설정 ---
gemini_api_key = os.getenv("GEMINI_API_KEY")
tmdb_api_key = os.getenv("TMDB_API_KEY")

if not gemini_api_key:
    logging.error("GEMINI_API_KEY가 설정되지 않았습니다.")
else:
    genai.configure(api_key=gemini_api_key)

# --- OTT 공급자 ID 매핑 ---
OTT_PROVIDERS = {
    "Netflix": 8,
    "Watcha": 97,
    "Wavve": 356,
    "Disney+": 337,
    "Apple TV+": 350,
    "Amazon Prime": 119,
}

# --- 데이터 모델 ---
class DiaryRequest(BaseModel):
    diary: str
    ott_filters: list[str] = []

# --- 상수 데이터 ---
EMOTION_GENRE_MAP = {
    "기쁨": [35, 10751], "행복": [35, 10751, 10749],
    "슬픔": [18, 10749, 10751], "분노": [28, 53, 80],
    "놀람": [9648, 878, 14], "평온": [10749, 16, 99],
    "사랑": [10749, 10751, 18], "지루함": [12, 878, 28],
}

EMOTION_REASON_MAP = {
    "기쁨": "오늘의 즐거움을 더해줄 유쾌한 영화들이에요!",
    "행복": "당신의 행복한 미소를 지켜줄 따뜻한 이야기입니다.",
    "슬픔": "지친 마음에 위로가 되어줄 감동적인 작품들이에요.",
    "분노": "스트레스를 날려버릴 짜릿한 액션을 준비했어요!",
    "놀람": "심장을 쫄깃하게 만들 반전과 스릴을 즐겨보세요.",
    "평온": "차분한 당신의 하루를 마무리할 잔잔한 영화입니다.",
    "사랑": "달달한 로맨스로 설렘을 충전해보는 건 어때요?",
    "지루함": "무료한 시간을 순삭시켜줄 흥미진진한 모험을 떠나봐요!",
}

# --- 전역 변수: 사용할 모델 이름 ---
SELECTED_MODEL_NAME = "gemini-2.5-flash" # 기본값 설정 (실패 시 대비)

def find_best_available_model():
    """사용 가능한 모델 목록을 조회하여 최적의 모델(2.5 버전 우선)을 선택합니다."""
    global SELECTED_MODEL_NAME
    try:
        logging.info("사용 가능한 Gemini 모델을 검색 중입니다...")
        available_models = []
        # 모델 목록 조회
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
        
        # [로그 수정] 검색된 모델 목록을 즉시 출력
        logging.info(f"검색된 모델 목록: {available_models}")

        # [우선순위 수정] 2025년 기준 최신 모델 우선순위 (사용자 로그 기반)
        priority_models = [
            "models/gemini-2.5-flash",          # 1순위: 밸런스 최강
            "models/gemini-2.5-pro",            # 2순위: 고성능
            "models/gemini-3-pro-preview",      # 3순위: 차세대 미리보기
            "models/gemini-2.0-flash",          # 4순위: 안정적인 구버전
            "models/gemini-2.0-flash-exp",      # 5순위
        ]

        # 우선순위 목록 순회하며 매칭
        for priority in priority_models:
            if priority in available_models:
                SELECTED_MODEL_NAME = priority
                logging.info(f"✅ 모델 자동 선택 완료: {SELECTED_MODEL_NAME}")
                return

        # 우선순위 모델이 없을 경우 목록의 첫 번째 선택
        if available_models:
             SELECTED_MODEL_NAME = available_models[0]
             logging.info(f"⚠️ 우선순위 모델(2.5/3.0)을 찾지 못해 목록의 첫 번째 모델 선택: {SELECTED_MODEL_NAME}")
        else:
             logging.error("❌ 사용 가능한 모델이 하나도 검색되지 않았습니다. API 키 권한을 확인해주세요.")

    except Exception as e:
        logging.error(f"모델 목록 조회 중 오류 발생: {e}")
        logging.info(f"기본값({SELECTED_MODEL_NAME})을 사용합니다.")

# 서버 시작 시 모델 찾기 실행
if gemini_api_key:
    find_best_available_model()

# --- 핵심 로직 ---
async def analyze_emotion_with_gemini(diary: str) -> str | None:
    # 선택된 최신 모델 사용
    model = genai.GenerativeModel(SELECTED_MODEL_NAME)
    
    prompt = (
        f"사용자의 일기를 읽고 핵심 감정을 다음 중 하나만 선택해서 단답형으로 대답해줘: "
        f"{', '.join(EMOTION_GENRE_MAP.keys())}.\n"
        f"일기 내용: {diary}\n"
        f"답변(단어 하나만):"
    )
    try:
        response = await model.generate_content_async(prompt)
        emotion = response.text.strip()
        for key in EMOTION_GENRE_MAP.keys():
            if key in emotion:
                return key
        return random.choice(list(EMOTION_GENRE_MAP.keys()))
    except Exception as e:
        logging.error(f"Gemini API Error ({SELECTED_MODEL_NAME}): {e}")
        return None

async def get_movie_recommendation(genre_ids: list[int], ott_provider_ids: list[int] = None, num_movies: int = 3):
    all_movies = []
    min_vote_count = 300 
    min_vote_average = 6.0 
    sort_options = ["popularity.desc", "vote_average.desc", "vote_count.desc"]
    selected_sort_by = random.choice(sort_options)

    for genre_id in genre_ids:
        if len(all_movies) >= num_movies * 5: break
        for page in range(1, 4): 
            url = f"https://api.themoviedb.org/3/discover/movie?api_key={tmdb_api_key}&with_genres={genre_id}&language=ko-KR&sort_by={selected_sort_by}&vote_count.gte={min_vote_count}&vote_average.gte={min_vote_average}&page={page}"
            
            if ott_provider_ids:
                providers_str = "|".join(map(str, ott_provider_ids))
                url += f"&with_watch_providers={providers_str}&watch_region=KR"

            try:
                response = requests.get(url)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('results'): 
                        for movie in data['results']:
                            if not movie.get('overview'): continue
                            if not movie.get('poster_path'): continue
                            all_movies.append(movie)
                    else: break
            except: break

    unique_movies = []
    seen_ids = set()
    for movie in all_movies:
        if movie['id'] not in seen_ids:
            unique_movies.append(movie)
            seen_ids.add(movie['id'])

    if len(unique_movies) < num_movies:
        fallback_url = f"https://api.themoviedb.org/3/discover/movie?api_key={tmdb_api_key}&language=ko-KR&sort_by=popularity.desc&page=1"
        if ott_provider_ids:
            providers_str = "|".join(map(str, ott_provider_ids))
            fallback_url += f"&with_watch_providers={providers_str}&watch_region=KR"
        
        try:
            res = requests.get(fallback_url)
            if res.status_code == 200:
                populars = res.json().get('results', [])
                for movie in populars:
                    if movie['id'] not in seen_ids and movie.get('overview') and movie.get('poster_path'):
                        unique_movies.append(movie)
                        seen_ids.add(movie['id'])
        except: pass

    if not unique_movies: return [] 
    return random.sample(unique_movies, min(num_movies, len(unique_movies)))

@app.post("/api/recommend-movie")
async def recommend_movie_endpoint(request: DiaryRequest):
    if not request.diary.strip():
        raise HTTPException(status_code=400, detail="일기 내용을 적어주세요.")
    
    ott_ids = []
    if request.ott_filters:
        for ott_name in request.ott_filters:
            if ott_name in OTT_PROVIDERS:
                ott_ids.append(OTT_PROVIDERS[ott_name])

    emotion = await analyze_emotion_with_gemini(request.diary)
    display_emotion = emotion if emotion else f"{random.choice(list(EMOTION_GENRE_MAP.keys()))} (랜덤)"
    
    genre_ids = EMOTION_GENRE_MAP.get(display_emotion.split()[0], [18])
    movies = await get_movie_recommendation(genre_ids, ott_provider_ids=ott_ids, num_movies=3)
    
    return {
        "emotion": display_emotion,
        "movies": movies,
        "reason": EMOTION_REASON_MAP.get(display_emotion.split()[0], "추천 영화입니다.")
    }

@app.get("/api/search-movies")
async def search_movies(query: str):
    if not query.strip():
        raise HTTPException(status_code=400, detail="검색어가 비어있습니다.")

    url = f"https://api.themoviedb.org/3/search/movie?api_key={tmdb_api_key}&query={query}&language=ko-KR"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return {"results": response.json().get('results', [])}
    except requests.RequestException as error:
        logging.error("TMDB 영화 검색 API 오류: %s", error)
        raise HTTPException(status_code=500, detail="영화 검색 중 오류가 발생했습니다.") from error

@app.get("/api/movie-details/{movie_id}")
async def get_movie_details(movie_id: int):
    url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={tmdb_api_key}&language=ko-KR&append_to_response=credits,watch/providers"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as error:
        logging.error("TMDB 영화 상세 API 오류: %s", error)
        raise HTTPException(status_code=500, detail="영화 상세 정보를 가져오는 중 오류가 발생했습니다.") from error

@app.get("/")
def read_root():
    return {"Hello": f"Movie Diary API is Running! (Model: {SELECTED_MODEL_NAME})"}
