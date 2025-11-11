from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

# ===== JWT 설정 =====
SECRET_KEY = "super-secret-key-change-this"  # 실제 서비스에서는 환경변수로 관리 권장
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# ===== FastAPI 앱 =====
app = FastAPI()

# OAuth2 스펙에 맞는 토큰 전달 방식 (Authorization: Bearer <token>)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# 비밀번호 해시용 컨텍스트 (bcrypt 대신 호환성 좋은 pbkdf2_sha256 사용)
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# ===== 요청 스키마 =====


class LoginRequest(BaseModel):
    username: str
    password: str


# ===== 가짜 유저 DB (실습용) =====
fake_user_db = {
    "testuser": {
        "username": "testuser",
        # 비밀번호: "testpassword" 를 bcrypt로 해시한 예시
        "hashed_password": pwd_context.hash("testpassword"),
        "full_name": "Test User",
        "disabled": False,
    }
}


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_user(db, username: str):
    user = db.get(username)
    return user


def authenticate_user(username: str, password: str):
    user = get_user(fake_user_db, username)
    if not user:
        return None
    if not verify_password(password, user["hashed_password"]):
        return None
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    # payload에 만료 시간(exp) 추가
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)  # 기본 15분
    to_encode.update({"exp": expire})
    # JWT 생성
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


@app.post("/login")
def login(login_request: LoginRequest):
    user = authenticate_user(login_request.username, login_request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 토큰 만료 시간 설정
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    # sub(Subject)로 username 담기
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # 토큰 디코딩
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        # 토큰이 만료되었거나 위조되었을 때
        raise credentials_exception

    user = get_user(fake_user_db, username)
    if user is None:
        raise credentials_exception
    return user


@app.get("/users/me")
async def read_users_me(current_user: dict = Depends(get_current_user)):
    return {
        "username": current_user["username"],
        "full_name": current_user["full_name"],
    }


@app.get("/secret")
async def read_secret(current_user: dict = Depends(get_current_user)):
    message = (
        f"Hello, {current_user['username']}! This is a secret endpoint."
    )
    return {"message": message}

#  python -m uvicorn main:app --reload