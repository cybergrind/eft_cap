git pull -r
.\venv\Scripts\pip.exe install -r requirements.txt

cd frontend
npm i
npm run build
cd ..
cd LeakedServer
git pull -r
cd ..
