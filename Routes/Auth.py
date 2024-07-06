from fastapi import APIRouter, Depends, status, HTTPException, Response
from fastapi.security.oauth2 import OAuth2PasswordRequestForm
from fastapi.security import OAuth2PasswordBearer

from dbConfig.database import user_collection

user_auth_route = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/workmateai/user/login') #the token is the route where we will do our user authentication and get the token
