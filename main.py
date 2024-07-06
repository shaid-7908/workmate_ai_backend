from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

#import all routes here
from Routes.User_Login_Register.user_login_register import UserLoginAndRegisterRouter
from Routes.Knowledgebase.Knowledge_base import knowledgeBaseRouter

app = FastAPI()

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#include router here
app.include_router(UserLoginAndRegisterRouter)
app.include_router(knowledgeBaseRouter)

@app.post('/token')
async def token():
    return True

@app.get("/")
def read_root():
    return {"message": "Hello, World!"}

@app.get("/items/{item_id}")
def read_item(item_id: int, q: str = None):
    return {"item_id": item_id, "q": q}
