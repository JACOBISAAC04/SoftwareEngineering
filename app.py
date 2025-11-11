import os
from flask import Flask, request, render_template
from supabase import create_client, Client
from dotenv import load_dotenv
import uuid

load_dotenv()

app = Flask(__name__)

supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

bucket = os.getenv("BUCKET_NAME")

@app.route("/", methods=["GET", "POST"])
def upload_file():
    if request.method == "POST":
        file = request.files["file"]

        if file and file.filename.endswith(".pdf"):
            unique_name = f"{uuid.uuid4()}.pdf"

            supabase.storage.from_(bucket).upload(unique_name, file.read())

            public_url = supabase.storage.from_(bucket).get_public_url(unique_name)

            # save link to DB
            supabase.table("documents").insert({
    "filename": file.filename,
    "storage_path": unique_name,
    "file_url": public_url
}).execute()


            return f"Uploaded ✅ <br> <a href='{public_url}'>Open PDF</a>"

        return "Only PDF allowed ❌"

    return render_template("upload.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

