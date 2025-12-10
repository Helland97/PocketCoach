To start this project you need to run 3 terminal. 

#Terminal 1 - Backend
1. change folder to AI/OlympicAi/Backend 
2. dotnet run 

#Terminal 2 - Fast API

if all dependencies is not ready you need to run: 
- python3 -m venv venv
- source venv/bin/activate
- pip install uvicorn opencv-python
- pip install fastapi
- pip install mediapipe
- pip install python-multipart


1. Change folder to AI/OlympicAI
2. run uvicorn Backend.main:app --reload

#Terminal 3 - Frontend

1. Change folder to frontend 
2. run "npm install"
3. run "npm run dev"

To stop running processes, control + c