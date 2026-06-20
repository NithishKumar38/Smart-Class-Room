@echo off
cd /d "d:\projects\Projects\smart classroom"
call venv\Scripts\activate.bat
echo Starting AI Classroom Co-Pilot...
echo App running at: http://localhost:8501
streamlit run app.py
pause
