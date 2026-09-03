(function() {
  // Set current year
  var yearEl = document.getElementById('year');
  if (yearEl) yearEl.textContent = new Date().getFullYear();

  // SIDEBAR
  var sidebar = document.getElementById('sidebar');
  var overlay = document.getElementById('sidebarOverlay');
  var hamburger = document.getElementById('hamburgerBtn');
  var closeSidebarBtn = document.getElementById('closeSidebarBtn');
  var sidebarInternalToggle = document.getElementById('sidebarInternalToggle');

  function openSidebar() {
    if (sidebar) sidebar.classList.add('open');
    if (overlay) overlay.classList.add('active');
    if (closeSidebarBtn) closeSidebarBtn.style.display = 'flex';
  }
  function closeSidebarFn() {
    if (sidebar) sidebar.classList.remove('open');
    if (overlay) overlay.classList.remove('active');
    if (closeSidebarBtn) closeSidebarBtn.style.display = 'none';
  }
  function toggleSidebar() {
    if (sidebar && sidebar.classList.contains('open')) {
      closeSidebarFn();
    } else {
      openSidebar();
    }
  }

  if (hamburger) hamburger.addEventListener('click', openSidebar);
  if (closeSidebarBtn) closeSidebarBtn.addEventListener('click', closeSidebarFn);
  if (overlay) overlay.addEventListener('click', closeSidebarFn);
  if (sidebarInternalToggle) sidebarInternalToggle.addEventListener('click', toggleSidebar);

  // LANGUAGE DROPDOWN
  var languageDropdown = document.getElementById('languageDropdown');
  var languageOptions = document.getElementById('languageOptions');
  var langChevron = document.getElementById('langChevron');
  if (languageDropdown && languageOptions) {
    languageDropdown.addEventListener('click', function(e) {
      e.preventDefault();
      if (languageOptions.style.display === 'none') {
        languageOptions.style.display = 'flex';
        if (langChevron) langChevron.textContent = 'expand_less';
      } else {
        languageOptions.style.display = 'none';
        if (langChevron) langChevron.textContent = 'expand_more';
      }
    });
  }

  // ----- GLOBAL DATA STATE -----
  var currentPlantFile = null;
  var lastResultHistoryId = null;
  var lastResultPlantId = null;

  // Helper to fetch CSRF token
  function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      var cookies = document.cookie.split(';');
      for (var i = 0; i < cookies.length; i++) {
        var cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  // Clear outdated session storage to force re-fetch
  var saved = sessionStorage.getItem('savedPlantResult');
  if (saved) {
    try {
      var savedObj = JSON.parse(saved);
      if (savedObj && !savedObj.benefits_sw) {
        sessionStorage.removeItem('savedPlantResult');
        sessionStorage.removeItem('savedPlantImage');
      }
    } catch(e) {}
  }

  // Helper to update Result UI
  function updateResultUI(plant) {
    var localNameTitle = document.getElementById('localNameTitle');
    var sciNameText = document.getElementById('sciNameText');
    var comNameText = document.getElementById('comNameText');
    var medUsesContainer = document.getElementById('medUsesContainer');
    var isSw = document.documentElement.lang && document.documentElement.lang.startsWith('sw');

    if (localNameTitle) {
      localNameTitle.textContent = plant.local_name;
    }
    if (sciNameText) sciNameText.textContent = plant.scientific_name;
    if (comNameText) comNameText.textContent = plant.common_name || 'N/A';
    
    if (medUsesContainer) {
      var html = '<div style="display:flex; flex-direction:column; gap:14px; margin-top:14px; text-align:left;">';
      
      // Helper to format text intelligently
      function autoFormatText(text) {
        if (!text) return '';
        let formatted = text;
        // Ensure "What to do", "How to use", etc. start on a new line without a gap and are bold
        formatted = formatted.replace(/(?:\r?\n)*\s*(What to do:|Nini cha kufanya:|How to use:|Jinsi ya kutumia:)/gi, '\n<strong>$1</strong> ');
        // Ensure numbered lists "1. ", "2. " start on a new paragraph (with a gap) and make the number bold
        formatted = formatted.replace(/(?:\r?\n)*\s*(\d+\.\s+[A-Z])/g, '\n\n<strong>$1</strong>');
        return formatted.trim();
      }

      // Render benefits
      var currentBenefits = isSw ? (plant.benefits_sw || plant.benefits) : (plant.benefits_en || plant.benefits);
      if (currentBenefits) {
        currentBenefits = autoFormatText(currentBenefits);
        html += '<div><strong>🌿 ' + (isSw ? 'Faida za Mmea:' : 'Benefits of the Plant:') + '</strong>' +
                '<div style="margin-top:6px; font-size:0.95rem; line-height:1.6; color:#2c3e35; font-weight:500; white-space: pre-wrap;">' + currentBenefits + '</div></div>';
      }
      
      // Render medicinal uses (supports HTML content from database)
      var currentMedUses = isSw ? (plant.medicinal_uses_sw || plant.medicinal_uses) : (plant.medicinal_uses_en || plant.medicinal_uses);
      if (currentMedUses) {
        currentMedUses = autoFormatText(currentMedUses);
        html += '<div style="margin-top:10px;"><strong>💊 ' + (isSw ? 'Matibabu ya Dawa:' : 'Medicinal Treatments:') + '</strong>' +
                '<div style="margin-top:6px; font-size:0.95rem; line-height:1.6; color:#2c3e35; font-weight:500; white-space: pre-wrap;">' + currentMedUses + '</div></div>';
      }

      // Render precautions
      var currentPrecautions = isSw ? (plant.precautions_sw || plant.precautions) : (plant.precautions_en || plant.precautions);
      if (currentPrecautions) {
          currentPrecautions = autoFormatText(currentPrecautions);
          html += '<div style="margin-top:10px;"><strong>⚠️ ' + (isSw ? 'Tahadhari:' : 'Precautions:') + '</strong>' +
                  '<div style="margin-top:6px; padding: 12px 14px; border-radius: 10px; background-color: #fff3f3; border-left: 4px solid #d32f2f; font-size:0.95rem; line-height:1.6; color:#c62828; font-weight:500; white-space: pre-wrap;">' + currentPrecautions + '</div></div>';
      }
      
      html += '</div>';
      medUsesContainer.innerHTML = html;
    }

    // Save to session storage for persistence
    sessionStorage.setItem('savedPlantResult', JSON.stringify(plant));
    var resultImage = document.getElementById('resultImage');
    if (resultImage) {
        sessionStorage.setItem('savedPlantImage', resultImage.innerHTML);
    }
    var cancelBtn = document.getElementById('cancelResultBtn');
    if (cancelBtn) cancelBtn.style.display = 'flex';
  }

  // ----- UPLOAD IMAGE FUNCTIONALITY -----
  var fileInput = document.getElementById('fileInput');
  var uploadBtn = document.getElementById('uploadBtn');
  var resultImage = document.getElementById('resultImage');

  function prepareForIdentification() {
    var resultCard = document.getElementById('resultCard');
    var identifyBtn = document.getElementById('identifyBtn');
    if (resultCard) {
      resultCard.classList.add('visible');
      resultCard.scrollIntoView({ behavior: 'smooth' });
    }
    if (identifyBtn) {
      identifyBtn.style.display = 'flex';
      identifyBtn.innerHTML = '<span class="material-icons">travel_explore</span> ' + (document.documentElement.lang && document.documentElement.lang.startsWith('sw') ? 'Tambua Mmea' : 'Identify Plant');
      identifyBtn.disabled = false;
    }
  }

  if (uploadBtn && fileInput) {
    uploadBtn.addEventListener('click', function() {
      fileInput.click();
    });
  }

  if (fileInput) {
    fileInput.addEventListener('change', function(e) {
      var file = e.target.files[0];
      if (file && resultImage) {
        currentPlantFile = file; // Store the file for upload
        var reader = new FileReader();
        reader.onload = function(event) {
          var img = document.createElement('img');
          img.src = event.target.result;
          img.alt = 'Uploaded plant';
          resultImage.innerHTML = '';
          resultImage.appendChild(img);
          prepareForIdentification();
        };
        reader.readAsDataURL(file);
      }
      fileInput.value = '';
    });
  }

  // ----- CAMERA FUNCTIONALITY -----
  var cameraContainer = document.getElementById('cameraContainer');
  var video = document.getElementById('video');
  var cameraBtn = document.getElementById('cameraBtn');
  var captureBtn = document.getElementById('captureBtn');
  var closeCameraBtn = document.getElementById('closeCameraBtn');
  var stream = null;

  if (cameraBtn) {
    cameraBtn.addEventListener('click', async function() {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ 
          video: { facingMode: 'environment' },
          audio: false 
        });
        if (video) video.srcObject = stream;
        if (cameraContainer) cameraContainer.classList.add('active');
      } catch (err) {
        if(window.showToast) showToast('Unable to access camera. Please allow camera permissions.', 'error'); else alert('❌ ' + err.message);
      }
    });
  }

  function closeCamera() {
    if (stream) {
      stream.getTracks().forEach(function(track) { track.stop(); });
      stream = null;
    }
    if (video) video.srcObject = null;
    if (cameraContainer) cameraContainer.classList.remove('active');
  }

  if (closeCameraBtn) closeCameraBtn.addEventListener('click', closeCamera);

  if (captureBtn) {
    captureBtn.addEventListener('click', function() {
      var canvas = document.createElement('canvas');
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      var ctx = canvas.getContext('2d');
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      
      // Convert canvas content to blob for uploading
      canvas.toBlob(function(blob) {
        currentPlantFile = blob;
      }, 'image/jpeg');
      
      var imageDataUrl = canvas.toDataURL('image/jpeg');

      if (resultImage) {
        var img = document.createElement('img');
        img.src = imageDataUrl;
        img.alt = 'Captured plant';
        resultImage.innerHTML = '';
        resultImage.appendChild(img);
      }

      prepareForIdentification();
      closeCamera();
    });
  }

  // ----- IDENTIFY BUTTON FUNCTIONALITY -----
  var identifyBtn = document.getElementById('identifyBtn');
  var resultDetails = document.getElementById('resultDetails');
  
  if (identifyBtn) {
    identifyBtn.addEventListener('click', function() {
      if (!currentPlantFile) {
        if(window.showToast) showToast(document.documentElement.lang === 'sw' ? 'Hakuna picha iliyochaguliwa.' : 'No image selected.', 'error'); else alert('No image selected.');
        return;
      }

      // Show loading
      identifyBtn.innerHTML = '<span class="material-icons">sync</span> ' + (document.documentElement.lang === 'sw' ? 'Inatambua...' : 'Identifying...');
      identifyBtn.disabled = true;

      // Prepare payload using FormData
      var formData = new FormData();
      if (currentPlantFile instanceof Blob && !(currentPlantFile instanceof File)) {
        formData.append('image', currentPlantFile, 'captured_plant.jpg');
      } else {
        formData.append('image', currentPlantFile);
      }

      fetch('/api/identify/', {
        method: 'POST',
        headers: {
          'X-CSRFToken': getCookie('csrftoken')
        },
        body: formData
      })
      .then(function(r) {
        return r.json().catch(function() {
          throw new Error('Server error (' + r.status + '). Please try again.');
        }).then(function(data) {
          if (!r.ok) {
            throw new Error(data.error || 'Server error (' + r.status + ').');
          }
          return data;
        });
      })
      .then(function(data) {
        identifyBtn.innerHTML = '<span class="material-icons">travel_explore</span> ' + (document.documentElement.lang && document.documentElement.lang.startsWith('sw') ? 'Tambua Mmea' : 'Identify Plant');
        identifyBtn.disabled = false;

        var inlineMsg = document.getElementById('inlineMessageContainer');

        if (data.error) {
          if (inlineMsg) {
              inlineMsg.style.display = 'block';
              inlineMsg.style.backgroundColor = '#fce4e4';
              inlineMsg.style.color = '#d32f2f';
              inlineMsg.style.border = '1px solid #f5c2c2';
              inlineMsg.innerHTML = '<span class="material-icons" style="vertical-align: middle; margin-right: 8px;">error</span>' + data.error;
              setTimeout(function() { inlineMsg.style.display = 'none'; }, 4000);
          } else {
              if(window.showToast) showToast(data.error, 'error'); else alert('❌ ' + data.error);
          }
          return;
        }

        if (inlineMsg) inlineMsg.style.display = 'none';

        // Store result IDs for saving later
        lastResultHistoryId = data.history_id;
        lastResultPlantId = data.id;

        // Render response data
        updateResultUI(data);
      })
      .catch(function(err) {
        identifyBtn.innerHTML = '<span class="material-icons">travel_explore</span> ' + (document.documentElement.lang && document.documentElement.lang.startsWith('sw') ? 'Tambua Mmea' : 'Identify Plant');
        identifyBtn.disabled = false;
        var inlineMsg = document.getElementById('inlineMessageContainer');
        if (inlineMsg) {
            inlineMsg.style.display = 'block';
            inlineMsg.style.backgroundColor = '#fce4e4';
            inlineMsg.style.color = '#d32f2f';
            inlineMsg.style.border = '1px solid #f5c2c2';
            inlineMsg.innerHTML = '<span class="material-icons" style="vertical-align: middle; margin-right: 8px;">error</span>' + err.message;
            setTimeout(function() { inlineMsg.style.display = 'none'; }, 4000);
        } else {
            if(window.showToast) showToast('Error: ' + err.message, 'error'); else alert('❌ Error: ' + err.message);
        }
      });
    });
  }

  if (cameraContainer) {
    cameraContainer.addEventListener('click', function(e) {
      if (e.target === cameraContainer) closeCamera();
    });
  }

  // ----- SEARCH FUNCTIONALITY -----
  var searchPlantBtn = document.getElementById('searchPlantBtn');
  var plantSearchInput = document.getElementById('plantSearchInput');

  function performSearch() {
    var query = plantSearchInput.value.trim();
    if (!query) {
      if(window.showToast) showToast(document.documentElement.lang && document.documentElement.lang.startsWith('sw') ? 'Tafadhali ingiza jina la mmea kwanza.' : 'Please enter a plant name first.', 'info'); else alert('Please enter a plant name first.');
      return;
    }
    
    // Loading state
    var originalBtnContent = searchPlantBtn.innerHTML;
    searchPlantBtn.innerHTML = '<span class="material-icons">sync</span> ' + (document.documentElement.lang === 'sw' ? 'Inatafuta...' : 'Searching...');
    searchPlantBtn.disabled = true;

    fetch('/api/search-plant/?q=' + encodeURIComponent(query))
      .then(function(r) { 
          if (!r.ok) {
              return r.json().then(err => { throw new Error(err.error || 'Hatujapata mmea huu.'); });
          }
          return r.json(); 
      })
      .then(function(plant) {
        searchPlantBtn.innerHTML = originalBtnContent;
        searchPlantBtn.disabled = false;

        var inlineMsg = document.getElementById('inlineMessageContainer');
        if (inlineMsg) inlineMsg.style.display = 'none';

        // Set IDs (null search history ID, but we keep plant ID for saving search snapshots)
        lastResultHistoryId = null;
        lastResultPlantId = plant.id || null;

        var resultCard = document.getElementById('resultCard');
        if (resultCard) {
          resultCard.classList.add('visible');
          resultCard.scrollIntoView({ behavior: 'smooth' });
        }

        // Render details
        updateResultUI(plant);

        // Update picture with Wikipedia image or default florist icon with a 2.5s delay
        var resultImage = document.getElementById('resultImage');
        if (resultImage) {
          // Show a loading spinner immediately
          resultImage.innerHTML = '<span class="material-icons notif-spin" style="font-size:48px; color:#2a7a2a;">autorenew</span>';
          
          // Delay the image rendering by 2.5 seconds
          setTimeout(function() {
            if (plant.image_url) {
              resultImage.innerHTML = '<img src="' + plant.image_url + '" alt="' + plant.local_name + '" />';
            } else {
              resultImage.innerHTML = '<span class="material-icons" style="font-size:64px; color:#2a7a2a;">local_florist</span>';
            }
          }, 2500);
        }

        // Keep identify button visible
        var identifyBtn = document.getElementById('identifyBtn');
        if (identifyBtn) identifyBtn.style.display = 'flex';
      })
      .catch(function(err) {
        searchPlantBtn.innerHTML = originalBtnContent;
        searchPlantBtn.disabled = false;
        var inlineMsg = document.getElementById('inlineMessageContainer');
        if (inlineMsg) {
            inlineMsg.style.display = 'block';
            inlineMsg.style.backgroundColor = '#fce4e4';
            inlineMsg.style.color = '#d32f2f';
            inlineMsg.style.border = '1px solid #f5c2c2';
            inlineMsg.innerHTML = '<span class="material-icons" style="vertical-align: middle; margin-right: 8px;">error</span>' + err.message;
            setTimeout(function() { inlineMsg.style.display = 'none'; }, 4000);
        } else {
            if(window.showToast) showToast(err.message, 'error'); else alert(err.message);
        }
      });
  }

  if (searchPlantBtn) {
    searchPlantBtn.addEventListener('click', performSearch);
  }
  if (plantSearchInput) {
    plantSearchInput.addEventListener('keypress', function(e) {
      if (e.key === 'Enter') performSearch();
    });
  }

  // ----- AUTO-SEARCH FROM URL PARAMETER -----
  var urlParams = new URLSearchParams(window.location.search);
  var searchQuery = urlParams.get('q');
  if (searchQuery && plantSearchInput && searchPlantBtn) {
    plantSearchInput.value = searchQuery;
    setTimeout(function() {
      performSearch();
    }, 300); // Slight delay for smoother transition
  }

  // ----- RESULT ACTIONS (auth-gated) -----
  var isAuthEl = document.getElementById('isAuthenticated');
  var registerUrlEl = document.getElementById('registerUrl');
  var isAuthenticated = isAuthEl ? isAuthEl.value === 'true' : false;
  var registerUrl = registerUrlEl ? registerUrlEl.value : '/register/';

  // Create the auth-required modal (injected once into the page)
  var authModal = document.createElement('div');
  authModal.id = 'authModal';
  authModal.innerHTML =
    '<div class="auth-modal-backdrop">' +
      '<div class="auth-modal-card">' +
        '<span class="material-icons auth-modal-icon">lock</span>' +
        '<h3>Registration Required</h3>' +
        '<p>You need to create an account first before you can use this feature.</p>' +
        '<div class="auth-modal-actions">' +
          '<a href="' + registerUrl + '" class="auth-modal-btn primary">Create Account</a>' +
          '<button class="auth-modal-btn secondary" id="authModalClose">Cancel</button>' +
        '</div>' +
      '</div>' +
    '</div>';
  document.body.appendChild(authModal);

  // Modal styles
  var modalStyle = document.createElement('style');
  modalStyle.textContent =
    '#authModal { display:none; position:fixed; top:0; left:0; width:100%; height:100%; z-index:9999; }' +
    '#authModal.active { display:block; }' +
    '.auth-modal-backdrop { width:100%; height:100%; background:rgba(0,0,0,0.5); display:flex; align-items:center; justify-content:center; animation:fadeIn .2s ease; }' +
    '.auth-modal-card { background:#fff; border-radius:20px; padding:2.5rem 2rem; max-width:380px; width:90%; text-align:center; box-shadow:0 20px 60px rgba(0,0,0,0.3); animation:slideUp .3s ease; }' +
    '.auth-modal-icon { font-size:48px; color:#e67e22; margin-bottom:12px; }' +
    '.auth-modal-card h3 { font-size:1.4rem; color:#1a3c34; margin-bottom:8px; font-weight:700; }' +
    '.auth-modal-card p { font-size:0.95rem; color:#555; margin-bottom:1.5rem; line-height:1.5; }' +
    '.auth-modal-actions { display:flex; gap:10px; justify-content:center; flex-wrap:wrap; }' +
    '.auth-modal-btn { padding:12px 28px; border-radius:30px; font-size:1rem; font-weight:600; cursor:pointer; text-decoration:none; border:none; transition:all .2s ease; }' +
    '.auth-modal-btn.primary { background:linear-gradient(135deg,#1f6b1f,#2b9a2b); color:#fff; box-shadow:0 6px 16px rgba(31,107,31,0.3); }' +
    '.auth-modal-btn.primary:hover { transform:scale(1.03); box-shadow:0 8px 20px rgba(31,107,31,0.4); }' +
    '.auth-modal-btn.secondary { background:#f0f0f0; color:#333; }' +
    '.auth-modal-btn.secondary:hover { background:#e0e0e0; }' +
    '@keyframes fadeIn { from{opacity:0} to{opacity:1} }' +
    '@keyframes slideUp { from{transform:translateY(30px);opacity:0} to{transform:translateY(0);opacity:1} }';
  document.head.appendChild(modalStyle);

  // Close modal handler
  document.getElementById('authModalClose').addEventListener('click', function() {
    authModal.classList.remove('active');
  });
  authModal.addEventListener('click', function(e) {
    if (e.target === authModal.querySelector('.auth-modal-backdrop')) {
      authModal.classList.remove('active');
    }
  });

  // Function to require auth or run action
  function requireAuth(actionFn) {
    if (isAuthenticated) {
      actionFn();
    } else {
      authModal.classList.add('active');
    }
  }

  // Attach to each button
  var saveBtn = document.getElementById('saveBtn');
  var printBtn = document.getElementById('printBtn');
  var pdfBtn = document.getElementById('pdfBtn');
  var shareBtn = document.getElementById('shareBtn');

  if (saveBtn) {
    saveBtn.addEventListener('click', function(e) {
      e.stopPropagation();
      requireAuth(function() {
        var payload = {};
        if (lastResultHistoryId) {
          payload.history_id = lastResultHistoryId;
        } else if (lastResultPlantId) {
          payload.plant_id = lastResultPlantId;
        } else {
          if(window.showToast) showToast(document.documentElement.lang === 'sw' ? 'Hakuna taarifa za mmea za kuhifadhi.' : 'No plant data to save.', 'error'); else alert('No plant data to save.');
          return;
        }

        saveBtn.disabled = true;

        fetch('/api/save/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
          },
          body: JSON.stringify(payload)
        })
        .then(function(r) { return r.json(); })
        .then(function(data) {
          saveBtn.disabled = false;
          if (data.status === 'ok') {
            if(window.showToast) showToast(document.documentElement.lang === 'sw' ? 'Taarifa zimehifadhiwa kikamilifu!' : 'Information saved successfully!', 'success'); else alert('✅ Information saved successfully!');
          } else {
            if(window.showToast) showToast(data.error || 'Failed to save.', 'error'); else alert('❌ ' + (data.error || 'Failed to save.'));
          }
        })
        .catch(function(err) {
          saveBtn.disabled = false;
          if(window.showToast) showToast('Error: ' + err.message, 'error'); else alert('❌ Error: ' + err.message);
        });
      });
    });
  }
  if (printBtn) {
    printBtn.addEventListener('click', function(e) {
      e.stopPropagation();
      requireAuth(function() {
        window.print();
      });
    });
  }

  if (pdfBtn) {
    pdfBtn.addEventListener('click', function(e) {
      e.stopPropagation();
      requireAuth(function() {
        if (typeof html2pdf === 'undefined') {
          if(window.showToast) showToast('PDF generator is loading... Please wait and try again.', 'info'); else alert('PDF generator is loading... Please wait and try again.');
          return;
        }

        var resultCard = document.getElementById('resultCard');
        if (!resultCard) return;

        var opt = {
          margin:       0.5,
          filename:     'PSIMIS_Plant_Information.pdf',
          image:        { type: 'jpeg', quality: 0.98 },
          html2canvas:  { 
            scale: 2,
            onclone: function(doc) {
              var clone = doc.getElementById('resultCard');
              if (clone) {
                var title = clone.querySelector('.print-only-title');
                if (title) title.style.display = 'block';
                
                var actions = clone.querySelector('.result-actions');
                if (actions) actions.style.display = 'none';

                var identifyBtn = clone.querySelector('#identifyBtn');
                if (identifyBtn) identifyBtn.style.display = 'none';
                
                var cancelBtnClone = clone.querySelector('#cancelResultBtn');
                if (cancelBtnClone) cancelBtnClone.style.display = 'none';

                clone.style.padding = '20px';
                clone.style.background = '#ffffff';
                clone.style.boxShadow = 'none';
                clone.style.color = '#000000'; // Force black text color
                
                // Force all child elements to have black text color too
                var allDescendants = clone.querySelectorAll('*');
                for(var i = 0; i < allDescendants.length; i++) {
                    allDescendants[i].style.color = '#000000';
                }
              }
            }
          },
          jsPDF:        { unit: 'in', format: 'letter', orientation: 'portrait' }
        };

        html2pdf().set(opt).from(resultCard).save();
      });
    });
  }

  if (shareBtn) {
    shareBtn.addEventListener('click', function(e) {
      e.stopPropagation();
      requireAuth(function() {
        var localName = document.getElementById('localNameTitle') ? document.getElementById('localNameTitle').innerText : '';
        var sciName = document.getElementById('sciNameText') ? document.getElementById('sciNameText').innerText : '';
        var comName = document.getElementById('comNameText') ? document.getElementById('comNameText').innerText : '';
        var usesText = document.getElementById('medUsesContainer') ? document.getElementById('medUsesContainer').innerText : '';

        var isSw = document.documentElement.lang === 'sw';
        var t_local = isSw ? 'Jina la Asili' : 'Local Name';
        var t_sci = isSw ? 'Jina la Kisayansi' : 'Scientific Name';
        var t_com = isSw ? 'Jina la Kawaida' : 'Common Name';

        var shareText = 'Plant Species Identification with Medicine Information System (PSIMIS)\n\n' +
                        t_local + ': ' + localName + '\n' +
                        t_sci + ': ' + sciName + '\n' +
                        t_com + ': ' + comName + '\n\n' +
                        usesText + '\n\n' +
                        'System Link: ' + window.location.href;

        if (navigator.share) {
          navigator.share({ title: 'PSIMIS Plant Identification', text: shareText }).catch(function(err) {
              console.log('Error sharing:', err);
          });
        } else {
          // Fallback
          navigator.clipboard.writeText(shareText).then(function() {
              if(window.showToast) showToast(isSw ? 'Taarifa zimenakiliwa tayari kwa kushare!' : 'Information copied to clipboard! You can paste it to share.', 'success'); else alert('📋 Copied!');
          });
        }
      });
    });
  }

  // ===== NOTIFICATION PANEL (Admin Only) =====
  var notifBellBtn = document.getElementById('notifBellBtn');
  var notifPanel = document.getElementById('notifPanel');
  var notifBadge = document.getElementById('notifBadge');
  var notifPanelBody = document.getElementById('notifPanelBody');
  var notifMarkAllBtn = document.getElementById('notifMarkAllBtn');

  if (notifBellBtn && notifPanel) {
    // Inject notification styles
    var notifStyle = document.createElement('style');
    notifStyle.textContent =
      '.notif-wrapper { position:relative; display:inline-flex; align-items:center; }' +
      '.notif-bell { background:none; border:none; cursor:pointer; position:relative; padding:6px; border-radius:50%; transition:background .2s; color:#153015; }' +
      '.notif-bell:hover { background:rgba(21,48,21,0.08); }' +
      '.notif-bell .material-icons { font-size:26px; }' +
      '.notif-badge { position:absolute; top:2px; right:2px; background:#e53935; color:#fff; font-size:11px; font-weight:700; min-width:18px; height:18px; line-height:18px; text-align:center; border-radius:9px; padding:0 5px; box-shadow:0 2px 6px rgba(229,57,53,0.4); pointer-events:none; }' +
      '.notif-panel { display:none; position:absolute; top:calc(100% + 8px); right:0; width:380px; max-height:480px; background:#fff; border-radius:16px; box-shadow:0 16px 48px rgba(0,0,0,0.18),0 4px 12px rgba(0,0,0,0.08); z-index:10000; overflow:hidden; border:1px solid #e8ece8; animation:notifSlideDown .25s ease; }' +
      '.notif-panel.open { display:block; }' +
      '.notif-panel-header { display:flex; justify-content:space-between; align-items:center; padding:16px 20px; border-bottom:1px solid #eef2ee; background:#f8fcf8; }' +
      '.notif-panel-header h4 { font-size:1rem; font-weight:700; color:#153015; margin:0; display:flex; align-items:center; }' +
      '.notif-mark-all { background:none; border:none; cursor:pointer; font-size:0.8rem; color:#2b7a2b; font-weight:600; display:flex; align-items:center; gap:4px; padding:6px 10px; border-radius:8px; transition:background .15s; }' +
      '.notif-mark-all:hover { background:#eaf3ea; }' +
      '.notif-panel-body { overflow-y:auto; max-height:380px; }' +
      '.notif-item { display:flex; gap:12px; padding:14px 20px; border-bottom:1px solid #f2f5f2; cursor:pointer; transition:background .15s; }' +
      '.notif-item:hover { background:#f6faf6; }' +
      '.notif-item.unread { background:#eef7ee; border-left:3px solid #2b7a2b; }' +
      '.notif-item.read { opacity:0.7; }' +
      '.notif-avatar { width:38px; height:38px; border-radius:50%; background:linear-gradient(135deg,#1f6b1f,#2b9a2b); display:flex; align-items:center; justify-content:center; flex-shrink:0; }' +
      '.notif-avatar .material-icons { color:#fff; font-size:20px; }' +
      '.notif-content { flex:1; min-width:0; }' +
      '.notif-subject { font-weight:600; font-size:0.9rem; color:#1a3c34; margin-bottom:3px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }' +
      '.notif-body { font-size:0.82rem; color:#555; line-height:1.4; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }' +
      '.notif-item.expanded .notif-subject { white-space:normal; overflow:visible; }' +
      '.notif-item.expanded .notif-body { display:block; -webkit-line-clamp:unset; overflow:visible; }' +
      '.notif-meta { display:flex; align-items:center; gap:6px; margin-top:5px; font-size:0.75rem; color:#888; }' +
      '.notif-empty { text-align:center; padding:40px 20px; color:#999; }' +
      '.notif-empty .material-icons { font-size:48px; color:#ccc; margin-bottom:8px; display:block; }' +
      '.notif-loading { text-align:center; padding:30px; color:#888; }' +
      '@keyframes notifSpin { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }' +
      '.notif-spin { animation:notifSpin 1s linear infinite; }' +
      '@keyframes notifSlideDown { from{opacity:0;transform:translateY(-8px)} to{opacity:1;transform:translateY(0)} }' +
      '@media(max-width:440px) { .notif-panel { width:calc(100vw - 20px); right:-60px; } }';
    document.head.appendChild(notifStyle);

    // Toggle panel
    notifBellBtn.addEventListener('click', function(e) {
      e.stopPropagation();
      var isOpen = notifPanel.classList.contains('open');
      if (isOpen) {
        notifPanel.classList.remove('open');
      } else {
        notifPanel.classList.add('open');
        loadNotifications();
      }
    });

    // Close when clicking outside
    document.addEventListener('click', function(e) {
      if (notifPanel.classList.contains('open') && !notifPanel.contains(e.target) && e.target !== notifBellBtn) {
        notifPanel.classList.remove('open');
      }
    });

    // Load notifications from API
    function loadNotifications() {
      notifPanelBody.innerHTML = '<div class="notif-loading"><span class="material-icons notif-spin">autorenew</span> Loading...</div>';
      fetch('/api/notifications/')
        .then(function(r) { return r.json(); })
        .then(function(data) {
          // Update badge
          updateBadge(data.unread_count);
          // Render messages
          if (data.messages.length === 0) {
            notifPanelBody.innerHTML =
              '<div class="notif-empty">' +
                '<span class="material-icons">notifications_off</span>' +
                'No messages yet' +
              '</div>';
            return;
          }
          var html = '';
          data.messages.forEach(function(m) {
            html +=
              '<div class="notif-item unread" data-id="' + m.id + '">' +
                '<div class="notif-avatar"><span class="material-icons">person</span></div>' +
                '<div class="notif-content">' +
                  '<div class="notif-subject">' + escapeHtml(m.subject) + '</div>' +
                  '<div class="notif-body">' + escapeHtml(m.body) + '</div>' +
                  '<div class="notif-meta">' +
                    '<span class="material-icons" style="font-size:14px;">person_outline</span> ' + escapeHtml(m.user) +
                    ' &nbsp;·&nbsp; <span class="material-icons" style="font-size:14px;">schedule</span> ' + m.created_at +
                  '</div>' +
                '</div>' +
              '</div>';
          });
          notifPanelBody.innerHTML = html;

          // Click to mark as read, remove from panel, then open in inbox
          notifPanelBody.querySelectorAll('.notif-item').forEach(function(item) {
            item.addEventListener('click', function() {
              var id = this.getAttribute('data-id');
              var el = this;
              // Mark as read on server first
              fetch('/api/notifications/' + id + '/read/')
                .then(function(r) { return r.json(); })
                .then(function() {
                  window.location.href = '/inbox/?msg_id=' + id;
                })
                .catch(function() {
                  window.location.href = '/inbox/?msg_id=' + id;
                });
            });
          });
        })
        .catch(function() {
          notifPanelBody.innerHTML = '<div class="notif-empty">Failed to load notifications</div>';
        });
    }

    function updateBadge(count) {
      if (count > 0) {
        notifBadge.textContent = count;
        notifBadge.style.display = 'inline-block';
        notifBellBtn.querySelector('.material-icons').textContent = 'notifications_active';
      } else {
        notifBadge.style.display = 'none';
        notifBellBtn.querySelector('.material-icons').textContent = 'notifications_none';
      }
    }

    function markAsRead(id, el) {
      fetch('/api/notifications/' + id + '/read/')
        .then(function(r) { return r.json(); })
        .then(function() {
          // Fade out and remove from notification panel
          el.style.transition = 'opacity 0.3s ease, max-height 0.3s ease, padding 0.3s ease';
          el.style.opacity = '0';
          el.style.maxHeight = '0';
          el.style.padding = '0 20px';
          el.style.overflow = 'hidden';
          setTimeout(function() {
            el.remove();
            // Show empty state if no more items
            if (notifPanelBody.querySelectorAll('.notif-item').length === 0) {
              notifPanelBody.innerHTML =
                '<div class="notif-empty">' +
                  '<span class="material-icons">notifications_off</span>' +
                  'No new messages' +
                '</div>';
            }
          }, 300);
          var current = parseInt(notifBadge.textContent) || 0;
          updateBadge(Math.max(0, current - 1));
        });
    }

    // Mark all as read - remove all from notification panel
    notifMarkAllBtn.addEventListener('click', function() {
      fetch('/api/notifications/mark-all-read/')
        .then(function(r) { return r.json(); })
        .then(function() {
          // Fade out all items then remove them
          var items = notifPanelBody.querySelectorAll('.notif-item');
          items.forEach(function(item) {
            item.style.transition = 'opacity 0.3s ease';
            item.style.opacity = '0';
          });
          setTimeout(function() {
            notifPanelBody.innerHTML =
              '<div class="notif-empty">' +
                '<span class="material-icons">notifications_off</span>' +
                'No new messages' +
              '</div>';
          }, 300);
          updateBadge(0);
        });
    });

    function escapeHtml(text) {
      var div = document.createElement('div');
      div.appendChild(document.createTextNode(text));
      return div.innerHTML;
    }

  // Initial badge load on page load
    fetch('/api/notifications/')
      .then(function(r) { return r.json(); })
      .then(function(data) { updateBadge(data.unread_count); })
      .catch(function() {});
  }

  // --- RESULT PERSISTENCE AND CANCEL LOGIC ---
  var savedPlant = sessionStorage.getItem('savedPlantResult');
  var savedImage = sessionStorage.getItem('savedPlantImage');
  if (savedPlant) {
      try {
          var plantData = JSON.parse(savedPlant);
          updateResultUI(plantData);
          var resultImage = document.getElementById('resultImage');
          if (savedImage && resultImage) {
              resultImage.innerHTML = savedImage;
          }
      } catch (e) {
          console.error('Error restoring plant data:', e);
      }
  }

  var cancelResultBtn = document.getElementById('cancelResultBtn');
  if (cancelResultBtn) {
      cancelResultBtn.addEventListener('click', function() {
          sessionStorage.removeItem('savedPlantResult');
          sessionStorage.removeItem('savedPlantImage');
          
          var localNameTitle = document.getElementById('localNameTitle');
          if (localNameTitle) localNameTitle.textContent = '';
          var sciNameText = document.getElementById('sciNameText');
          if (sciNameText) sciNameText.textContent = '';
          var comNameText = document.getElementById('comNameText');
          if (comNameText) comNameText.textContent = '';
          
          var medUsesContainer = document.getElementById('medUsesContainer');
          if (medUsesContainer) {
              var isSw = document.documentElement.lang && document.documentElement.lang.startsWith('sw');
              medUsesContainer.innerHTML = '<span class="med-tag">🌿 ' + (isSw ? 'Matumizi ya dawa' : 'Medicinal uses') + '</span>';
          }
          
          var resultImage = document.getElementById('resultImage');
          if (resultImage) {
              resultImage.innerHTML = '<span class="material-icons" style="font-size:64px;" id="defaultIcon">spa</span>';
          }
      });
  }

  // ----- GLOBAL TOAST AUTO-HIDE -----
  var toasts = document.querySelectorAll('.toast-notification');
  toasts.forEach(function(toast) {
    setTimeout(function() {
      toast.classList.add('hide');
      setTimeout(function() {
        if (toast.parentElement) {
          toast.parentElement.removeChild(toast);
        }
      }, 500); // Wait for transition
    }, 4000);
  });

  // ----- CUSTOM CONFIRM MODAL -----
  var confirmModal = document.getElementById('customConfirmModal');
  var confirmMsgEl = document.getElementById('customConfirmMessage');
  var confirmCancelBtn = document.getElementById('customConfirmCancel');
  var confirmOkBtn = document.getElementById('customConfirmOk');
  var activeForm = null;

  if (confirmModal) {
    document.addEventListener('submit', function(e) {
      if (e.target && e.target.hasAttribute('data-confirm')) {
        e.preventDefault();
        activeForm = e.target;
        confirmMsgEl.textContent = activeForm.getAttribute('data-confirm');
        confirmModal.style.display = 'flex';
      }
    });

    confirmCancelBtn.addEventListener('click', function() {
      confirmModal.style.display = 'none';
      activeForm = null;
    });

    confirmOkBtn.addEventListener('click', function() {
      if (activeForm) {
        confirmModal.style.display = 'none';
        // Remove data-confirm so it doesn't trigger again, then submit
        var formToSubmit = activeForm;
        activeForm = null;
        formToSubmit.removeAttribute('data-confirm');
        formToSubmit.submit();
      }
    });
  }

})();
