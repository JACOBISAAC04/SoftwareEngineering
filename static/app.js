document.addEventListener('DOMContentLoaded', () => {
    
    // Get references to our HTML elements
    const fileInput = document.getElementById('file-input');
    const uploadButton = document.getElementById('upload-button');
    const statusLog = document.getElementById('status-log');
    const documentList = document.getElementById('document-list');

    let selectedFile = null;

    // --- Helper function to update the status log ---
    function log(message) {
        console.log(message);
        statusLog.textContent = message;
    }

    // --- Function to load all documents from our backend ---
    async function loadDocuments() {
        try {
            documentList.innerHTML = '<li>Loading...</li>';
            const response = await fetch('/api/get-documents');
            if (!response.ok) throw new Error('Failed to load documents.');
            
            const documents = await response.json();

            if (documents.length === 0) {
                documentList.innerHTML = '<li>No documents uploaded yet.</li>';
                return;
            }

            // Clear list and re-populate
            documentList.innerHTML = ''; 
            documents.forEach(doc => {
                const li = document.createElement('li');
                
                // Create a link that we can click on
                const a = document.createElement('a');
                a.href = '#'; // Placeholder
                a.textContent = doc.filename;
                // Store the path in the link, so we know what to fetch
                a.dataset.path = doc.storage_path; 
                a.classList.add('document-link'); // Add a class for styling/identification
                
                li.appendChild(a);
                documentList.appendChild(li);
            });
        } catch (error) {
            documentList.innerHTML = `<li>Error: ${error.message}</li>`;
        }
    }

    // --- Handle clicking on a document link to view it ---
    documentList.addEventListener('click', async (event) => {
        // Only act if the clicked item is a document link
        if (event.target.classList.contains('document-link')) {
            event.preventDefault(); // Stop the '#' link
            
            const link = event.target;
            const path = link.dataset.path;
            const originalText = link.textContent;
            
            link.textContent = 'Generating secure link...';

            try {
                // Ask our backend for a temporary download URL
                const response = await fetch('/api/get-download-link', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ storage_path: path })
                });

                if (!response.ok) throw new Error('Could not get download link.');

                const { download_url } = await response.json();
                
                // Open the secure link in a new tab! This solves your problem.
                window.open(download_url, '_blank');
                link.textContent = originalText; // Reset text
            
            } catch (error) {
                alert(error.message);
                link.textContent = originalText; // Reset text
            }
        }
    });

    // --- Handle selecting a file ---
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

    // --- Handle clicking the "Upload" button ---
    uploadButton.addEventListener('click', async () => {
        if (!selectedFile) return;

        log('Starting upload process...');
        uploadButton.disabled = true;
        let storagePath = ''; // We'll get this from our backend

        try {
            // STEP A: Get the secure upload URL from our Flask backend
            log('Asking our server for permission to upload...');
            const getUrlResponse = await fetch('/api/get-upload-link', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ filename: selectedFile.name }),
            });

            if (!getUrlResponse.ok) {
                const errorData = await getUrlResponse.json();
                throw new Error(errorData.error || 'Could not get upload URL from server.');
            }

            const { upload_url, storage_path } = await getUrlResponse.json();
            storagePath = storage_path; // Save this for Step C
            
            log('Permission granted. Uploading file directly to Supabase...');

            // STEP B: Upload the file DIRECTLY to Supabase (bypassing our server)
            const storageResponse = await fetch(upload_url, {
                method: 'PUT',
                body: selectedFile,
                headers: { 'Content-Type': selectedFile.type },
            });

            if (!storageResponse.ok) {
                throw new Error('File upload to Supabase Storage failed.');
            }
            log('File uploaded successfully!');

            // STEP C: Tell our server to save the file info to our database
            log('Saving file record to our database...');
            const recordResponse = await fetch('/api/record-document', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    filename: selectedFile.name,
                    storage_path: storagePath, 
                }),
            });

            if (!recordResponse.ok) {
                throw new Error('Could not save record to database.');
            }
            
            log('All done! File record saved.');
            
            loadDocuments(); // Refresh the list!

        } catch (error) {
            log(`An error occurred: ${error.message}`);
        } finally {
            // Reset the form
            uploadButton.disabled = false;
            fileInput.value = null;
            selectedFile = null;
        }
    });

    // --- Finally, load all documents when the page first loads ---
    loadDocuments();
});