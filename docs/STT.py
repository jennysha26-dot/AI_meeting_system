import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from openai import OpenAI
from dotenv import load_dotenv

# 載入環境變數（讀取 .env 檔案中的 API Key）
load_dotenv()

# 初始化 FastAPI 應用程式
app = FastAPI(title="會議系統 - STT 語音轉文字服務")

# 初始化 OpenAI 客戶端
# 程式會自動去讀取環境變數中的 OPENAI_API_KEY
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@app.post("/api/stt")
async def speech_to_text(file: UploadFile = File(...)):
    """
    【第一步：接球】接收前端傳過來的語音檔案
    """
    # 檢查前端有沒有傳檔案過來
    if not file:
        raise HTTPException(status_code=400, detail="請上傳語音檔案")
    
    print(f"成功接收檔案: {file.filename}，準備處理...")
    
    try:
        # 為了把檔案送給 OpenAI，我們需要先讀取這個檔案的內容
        # 這裡的 file.file.read() 是讀取二進位資料
        audio_bytes = await file.read()
        
        # 由於 OpenAI SDK 需要一個「有檔名」的檔案物件，我們用 tuple 包裹：(檔名, 檔案內容)
        file_tuple = (file.filename, audio_bytes)
        
        """
        【第二步：寄件】將檔案送往 OpenAI Whisper API
        """
        print("正在將檔案送往 Whisper 模型轉譯中，請稍候...")
        
        response = client.audio.transcriptions.create(
            model="whisper-1",       # 指定使用 Whisper 模型
            file=file_tuple,          # 傳入剛剛整理好的語音檔案
            language="zh"             # 強制指定轉成中文（可提升台灣國語、專有名詞的準確度）
        )
        
        # 取得轉譯後的文字結果
        transcript_text = response.text
        print("轉譯成功！")
        
        """
        【第三步：送貨】把結果回傳（未來要在這裡把資料傳給 Gemini 和 Database 隊友）
        """
        # TODO: 隊友的 Function 可以在這裡呼叫
        # gemini_result = call_gemini_summary(transcript_text)
        # save_to_db(transcript_text, gemini_result)
        
        # 目前先將結果回傳給前端確認
        return {
            "status": "success",
            "filename": file.filename,
            "transcript": transcript_text
        }

    except Exception as e:
        print(f"發生錯誤: {str(e)}")
        raise HTTPException(status_code=500, detail=f"STT 轉譯失敗: {str(e)}")

# 啟動伺服器的設定（方便你在 VS Code 直接執行此腳本）
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)