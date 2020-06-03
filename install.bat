python.exe -m venv venv

.\venv\Scripts\pip.exe install -r requirements.txt
cd frontend
npm i
npm run build
cd ..
