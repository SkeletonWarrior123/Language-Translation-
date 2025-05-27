from fastapi import FastAPI, HTTPException, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import time
from datetime import datetime, timedelta
from functools import lru_cache
import logging
from typing import Optional
import asyncio


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


GROQ_API_KEY = "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"  
MAX_RETRIES = 3
BASE_RETRY_DELAY = 2  
MAX_CHUNK_LENGTH = 350  
MIN_REQUEST_INTERVAL = 0.2  


rate_limit_expiry: Optional[datetime] = None
last_request_time: datetime = datetime.min

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Retry-After", "X-Translation-Time"]
)

class TranslationRequest(BaseModel):
    text: str

class TranslationResponse(BaseModel):
    translatedText: str
    warning: Optional[str] = None
    retryAfter: Optional[int] = None

@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    """Ensure CORS headers are added to all responses"""
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response

def split_text_into_chunks(text: str) -> list[str]:
    """Improved chunking that preserves sentence boundaries"""
    sentences = []
    current_sentence = []
    current_length = 0
    
    for word in text.split():
        word_length = len(word) + 1 
        
        if current_length + word_length > MAX_CHUNK_LENGTH and current_sentence:
            sentences.append(' '.join(current_sentence))
            current_sentence = []
            current_length = 0
            
        current_sentence.append(word)
        current_length += word_length
    
    if current_sentence:
        sentences.append(' '.join(current_sentence))
    
    return sentences

async def translate_chunk(chunk: str, attempt: int = 0) -> str:
    """Translate a single chunk with retry logic"""
    global rate_limit_expiry, last_request_time
    

    elapsed = (datetime.now() - last_request_time).total_seconds()
    if elapsed < MIN_REQUEST_INTERVAL:
        await asyncio.sleep(MIN_REQUEST_INTERVAL - elapsed)
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "TranslationService/1.0"
    }
    
    data = {
        "model": "meta-llama/llama-4-scout-17b-16e-instruct",
        "messages": [
            {
                "role": "system",
                "content": "You are a professional translator. Translate English to Hindi accurately. "
                          "Maintain original meaning, context and tone. Only return the Hindi translation."
            },
            {
                "role": "user",
                "content": f"Translate this to Hindi without any additional text:\n{chunk}"
            }
        ],
        "temperature": 0.3,
        "max_tokens": 1024
    }
    
    try:
        last_request_time = datetime.now()
        response = requests.post(url, headers=headers, json=data, timeout=20)
        
        if response.status_code == 429:
            retry_after = int(response.headers.get('Retry-After', BASE_RETRY_DELAY * (attempt + 1)))
            rate_limit_expiry = datetime.now() + timedelta(seconds=retry_after)
            raise requests.exceptions.HTTPError("Rate limited by API")
            
        response.raise_for_status()
        
        translated_text = response.json()["choices"][0]["message"]["content"].strip()
        return translated_text.strip('"')
        
    except requests.exceptions.RequestException as e:
        if attempt < MAX_RETRIES - 1:
            delay = BASE_RETRY_DELAY * (attempt + 1)
            logger.warning(f"Attempt {attempt + 1} failed. Retrying in {delay} seconds. Error: {str(e)}")
            await asyncio.sleep(delay)
            return await translate_chunk(chunk, attempt + 1)
        raise Exception(f"Failed after {MAX_RETRIES} attempts: {str(e)}")

@lru_cache(maxsize=1000)
async def translate_to_hindi(text: str) -> tuple[str, Optional[str]]:
    """Main translation function with chunking"""
    if not text.strip():
        return "", None
        
    chunks = split_text_into_chunks(text)
    translated_chunks = []
    warning = None
    
    for chunk in chunks:
        try:
            translated = await translate_chunk(chunk)
            translated_chunks.append(translated)
        except Exception as e:
            logger.error(f"Failed to translate chunk: {str(e)}")
            translated_chunks.append(f"[TRANSLATION FAILED: {chunk[:50]}...]")
            warning = "Partial translation: Some parts could not be translated"
    
    return ' '.join(translated_chunks), warning

@app.options("/translate")
async def options_translate():
    """Handle OPTIONS requests for CORS preflight"""
    return Response(
        content="OK",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        }
    )

@app.post("/translate", response_model=TranslationResponse)
async def translate_api(request: TranslationRequest, response: Response):
    start_time = time.time()
    
    if not request.text.strip():
        raise HTTPException(
            status_code=400,
            detail="No text provided",
            headers={"Access-Control-Allow-Origin": "*"}
        )
    
    try:
        
        if rate_limit_expiry and datetime.now() < rate_limit_expiry:
            retry_after = int((rate_limit_expiry - datetime.now()).total_seconds())
            response.headers.update({
                "Retry-After": str(retry_after),
                "Access-Control-Expose-Headers": "Retry-After"
            })
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Please try again in {retry_after} seconds.",
                headers={"Access-Control-Allow-Origin": "*"}
            )
            
        translated_text, warning = await translate_to_hindi(request.text)
        duration = time.time() - start_time
        
        response.headers.update({
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "public, max-age=3600",
            "X-Content-Type-Options": "nosniff",
            "X-Translation-Time": f"{duration:.2f}s",
            "Access-Control-Expose-Headers": "X-Translation-Time, Retry-After"
        })
        
        return TranslationResponse(
            translatedText=translated_text,
            warning=warning
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Translation error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred during translation. Please try again later.",
            headers={"Access-Control-Allow-Origin": "*"}
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000, reload=True)