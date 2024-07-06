from dotenv import load_dotenv
from typing import Annotated
from dbConfig.database import user_collection
from fastapi import APIRouter,UploadFile,Depends ,HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import timedelta
from Utils.user_login_and_verify import create_access_token
from models.models_schema import User
import bcrypt
import os

ACCESS_TOKEN_EXPIRE_MINUTES = os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES')

UserLoginAndRegisterRouter = APIRouter(
    prefix="/workmateai",
    tags=["User Authentication"],
    responses={404: {"description": "Not found"}},
)

@UserLoginAndRegisterRouter.post('/user/register')
async def register_user(user: User):
    # Check if the user already exists in the database
    if user_collection.find_one({"user_name": user.user_name}):
        raise HTTPException(status_code=400, detail="Username already registered")

    
    # Hash the user's password before storing it
    hashed_password = bcrypt.hashpw(user.user_password.encode('utf-8'), bcrypt.gensalt())

    # Create a user document to be inserted into the MongoDB collection
    user_data = {
        "name": user.name,
        "user_name": user.user_name,
        "user_email": user.user_email,
        "user_password": hashed_password,
        
    }


    # Insert the user data into the MongoDB collection
    result = user_collection.insert_one(user_data)
    
    # Generate a token for the registered user
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(data={"sub": user.user_name}, expires_delta=access_token_expires)

    # Return the registered user's details (excluding password) with a success message
    registered_user = {
        "name": user.name,
        "user_name": user.user_name,
        "user_email": user.user_email,
    }
    return {"message": "User registered successfully", "user": registered_user,"access_token":access_token}


@UserLoginAndRegisterRouter.post('/user/login')
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # Check if the user exists in the database
    stored_user = user_collection.find_one({"user_name": form_data.username})
    if not stored_user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Check if the password matches the hashed password in the database
    hashed_password = stored_user["user_password"]
    if not bcrypt.checkpw(form_data.password.encode('utf-8'), hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Generate a token for the authenticated user
    access_token_expires = timedelta(days=1)
    access_token = create_access_token(data={"sub": form_data.username,"user_id":str(stored_user["_id"])}, expires_delta=access_token_expires)

    return {"access_token": access_token, "token_type": "bearer"}