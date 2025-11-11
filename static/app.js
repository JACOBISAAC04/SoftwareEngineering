// Wait for the page to load
document.addEventListener('DOMContentLoaded', () => {
    
    const fileInput = document.getElementById('file-input');
    const uploadButton = document.getElementById('upload-button');
    const statusLog = document.getElementById('status-log');

    let selectedFile = null;

    function log(message) {
        console.log(message);
        statusLog.textContent = message;
    }

    // Enable the upload button when a file is selected
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            selectedFile = fileInput.files[0];
            log(`Selected file: ${selectedFile.name}`);
            uploadButton.disabled = false;
        } else {
            selectedFile = null;
            log('Please select a file...');
            uploadButton.disabled = true;
        }
    });

    // Handle the button click
    uploadButton.addEventListener('click', async () => {
        if (!selectedFile) return;

        log('Starting upload process...');
        uploadButton.disabled = true;

        try {
            // --- STEP A: Get the secure upload URL from our Flask backend ---
            log('Asking our server for permission to upload...');
            const getUrlResponse = await fetch('/api/get-upload-link', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    filename: selectedFile.name,
                    content_type: selectedFile.type,
                }),
            });

            if (!getUrlResponse.ok) {
                throw new Error('Could not get upload URL from server.');
            }

            const { signed_url } = await getUrlResponse.json();
            log('Permission granted. Uploading file to Firebase Storage...');

            // --- STEP B: Upload the file directly to Firebase Storage ---
            // We use the 'signed_url' from our backend.
            const storageResponse = await fetch(signed_url, {
                method: 'PUT',
                body: selectedFile,
                headers: {
                    // You might need to set the content-type here
                    // based on what your signed URL expects
                    'Content-Type': selectedFile.type,
                },
            });

            if (!storageResponse.ok) {
                throw new Error('File upload to Firebase Storage failed.');
            }
            log('File uploaded successfully!');

            // --- STEP C: Tell our server to save the file info to Firestore ---
            log('Saving file record to our database...');
            
            // Get the path of the file we just uploaded
            const storagePath = new URL(signed_url).pathname;

            const recordResponse = await fetch('/api/record-document', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    filename: selectedFile.name,
                    storage_path: storagePath,
                }),
            });

            if (!recordResponse.ok) {
                throw new Error('Could not save record to database.');
            }
            
            log('All done! File record saved.');

        } catch (error) {
            log(`An error occurred: ${error.message}`);
        } finally {
            // Reset
            uploadButton.disabled = false;
            fileInput.value = null;
            selectedFile = null;
        }
    });
});