# news/utils.py
from newsapi import NewsApiClient
from transformers import pipeline
import spacy
from geopy.geocoders import Nominatim
from .models import NewsArticle
from django.utils.dateparse import parse_datetime
from django.conf import settings
import time

# 초기화
newsapi = NewsApiClient(api_key=settings.NEWS_API_KEY)
nlp = spacy.load('en_core_web_sm')
geolocator = Nominatim(user_agent="news_geo_locator")
summarizer = pipeline("summarization", model="facebook/bart-large-cnn")

CATEGORIES = [
    'business',
    'entertainment',
    'general',
    'health',
    'science',
    'sports',
    'technology',
]


def extract_location(text):
    """텍스트에서 위치 엔티티 추출 및 지오코딩"""
    doc = nlp(text)
    for ent in doc.ents:
        if ent.label_ in ['GPE', 'LOC']:
            location = geolocator.geocode(ent.text, timeout=10)
            if location:
                return location.latitude, location.longitude
    return None, None


def compute_importance(article_text):
    """기사 텍스트로부터 요약과 중요도 계산"""
    try:
        # 입력 텍스트의 단어 수 확인
        input_length = len(article_text.split())

        # max_length를 입력 텍스트 길이에 따라 조정
        max_length = min(150, int(input_length * 0.8))  # 입력 길이의 80%로 제한
        min_length = max(40, int(input_length * 0.2))  # 입력 길이의 20%로 제한

        # 요약 생성
        summary_result = summarizer(
            article_text,
            max_length=max_length,
            min_length=min_length,
            do_sample=False
        )
        summary = summary_result[0]['summary_text']
    except Exception as e:
        print("요약 생성 중 오류 발생:", e)
        summary = ""
    importance_score = len(summary.split())
    return summary, importance_score


def fetch_and_store_top_headlines(language='en', page_size=100):
    for category in CATEGORIES:
        articles = newsapi.get_top_headlines(
            category=category,
            language=language,
            page_size=page_size,
            country='us'
        ).get('articles', [])

        for article in articles:
            url = article.get('url')
            if NewsArticle.objects.filter(url=url).exists():
                continue

            title = article.get('title', '')
            description = article.get('description', '')
            content = article.get('content', '')
            published_at = parse_datetime(article.get('publishedAt'))

            full_text = " ".join(filter(None, [title, description, content]))
            lat, lon = extract_location(full_text)
            summary, importance = compute_importance(full_text) if full_text else ("", 0)

            NewsArticle.objects.create(
                title=title,
                description=description,
                url=url,
                published_at=published_at,
                summary=summary,
                importance=importance,
                latitude=lat,
                longitude=lon,
                category=category
            )
