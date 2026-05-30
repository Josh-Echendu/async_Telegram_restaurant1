(function() {
    const MAIADDY_KEY = window.MAIADDY_TOKEN;
    const LOCATIONIQ_KEY = window.LOCATIONIQ_TOKEN;
    const GEOAPIFY_KEY = window.GEOAPIFY_TOKEN;
    
    if (!MAIADDY_KEY && !LOCATIONIQ_KEY && !GEOAPIFY_KEY) {
        console.error('🚀 [Autocomplete API]: No address API tokens found on window object.');
        return;
    }
    
    let debounceTimer = null;
    let currentFocus = -1;
    let input = null;
    let suggestionsContainer = null;
    
    // Independent request abortion controllers
    let maiaddyController = null;
    let locationiqController = null;
    let geoapifyController = null;
    
    function initAutocomplete() {
        input = document.getElementById('address-autocomplete');
        suggestionsContainer = document.getElementById('address-suggestions');
        
        if (!input || !suggestionsContainer) {
            console.log('🚀 [Autocomplete]: elements not yet in DOM, waiting...');
            return false;
        }
        
        input.removeEventListener('input', handleInput);
        input.removeEventListener('keydown', handleKeydown);
        
        input.addEventListener('input', handleInput);
        input.addEventListener('keydown', handleKeydown);
        
        console.log('🚀 [Autocomplete]: Initialized successfully (Maiaddy + LocationIQ + Geoapify Engine Running)');
        return true;
    }
    
    const observer = new MutationObserver(function() {
        if (!input || !document.body.contains(input)) {
            initAutocomplete();
        }
    });
    observer.observe(document.body, { childList: true, subtree: true });
    initAutocomplete();
    
    function handleInput(e) {
        const query = e.target.value.trim();
        clearTimeout(debounceTimer);
        
        if (query.length < 3) {
            suggestionsContainer.classList.add('hidden');
            suggestionsContainer.innerHTML = '';
            return;
        }
        
        debounceTimer = setTimeout(function() {
            fetchSuggestions(query);
        }, 500);
    }
    
    function fetchSuggestions(query) {
        // Abort all pending operations
        if (maiaddyController) maiaddyController.abort();
        if (locationiqController) locationiqController.abort();
        if (geoapifyController) geoapifyController.abort();
        
        maiaddyController = new AbortController();
        locationiqController = new AbortController();
        geoapifyController = new AbortController();
        
        suggestionsContainer.innerHTML = `
            <div class="px-4 py-3 text-sm text-[#6f7c91]">
                <i class="fas fa-spinner fa-pulse mr-2"></i>Searching addresses...
            </div>
        `;
        suggestionsContainer.classList.remove('hidden');
        
        let maiaddyDone = false;
        let locationiqDone = false;
        let geoapifyDone = false;
        
        let allResults = [];
        let maiaddyResults = [];
        let locationiqResults = [];
        let geoapifyResults = [];
        
        function renderAllResults() {
            // Only merge when all active requests conclude execution
            if (!maiaddyDone || !locationiqDone || !geoapifyDone) return;
            
            console.log(`📊 [Autocomplete UI]: Merging results. Maiaddy: ${maiaddyResults.length} | LocationIQ: ${locationiqResults.length} | Geoapify: ${geoapifyResults.length}`);
            
            const combinedResults = [...maiaddyResults];
            const uniqueStreets = new Set(maiaddyResults.map(r => (r.streetName || '').toLowerCase().trim()));
            
            // Merge LocationIQ unique hits
            locationiqResults.forEach(function(item) {
                const streetName = (item.address?.road || item.address?.pedestrian || item.display_name?.split(',')[0] || '').toLowerCase().trim();
                if (streetName && !uniqueStreets.has(streetName)) {
                    uniqueStreets.add(streetName);
                    combinedResults.push(item);
                }
            });
            
            // Merge Geoapify unique hits
            geoapifyResults.forEach(function(item) {
                const props = item.properties || {};
                const streetName = (props.street || props.name || props.formatted?.split(',')[0] || '').toLowerCase().trim();
                if (streetName && !uniqueStreets.has(streetName)) {
                    uniqueStreets.add(streetName);
                    combinedResults.push(item);
                }
            });
            
            allResults = combinedResults;
            console.log(`✨ [Autocomplete UI]: Total unique combined addresses to render: ${allResults.length}`);
            
            if (allResults.length === 0) {
                suggestionsContainer.innerHTML = `
                    <div class="px-4 py-3 text-sm text-[#6f7c91]">
                        <i class="fas fa-search mr-2"></i>No addresses found. Try a different search.
                    </div>
                `;
                return;
            }
            
            suggestionsContainer.innerHTML = '';
            
            allResults.forEach(function(item, index) {
                const source = item._source;
                let streetName = '', city = '', state = '', badge = '';
                
                if (source === 'maiaddy') {
                    streetName = item.streetName || '';
                    city = item.lga || '';
                    state = item.state || '';
                    badge = '📍 Maiaddy';
                } else if (source === 'locationiq') {
                    streetName = item.address?.road || item.address?.pedestrian || item.display_name?.split(',')[0] || '';
                    city = item.address?.city || item.address?.town || item.address?.village || '';
                    state = item.address?.state || '';
                    badge = '🌍 LocationIQ';
                } else if (source === 'geoapify') {
                    const props = item.properties || {};
                    streetName = props.street || props.name || props.formatted?.split(',')[0] || '';
                    city = props.city || props.county || '';
                    state = props.state || '';
                    badge = '✨ Geoapify';
                }
                
                const div = document.createElement('div');
                div.className = 'px-4 py-3 cursor-pointer border-b border-[#f0f4fa] last:border-0 hover:bg-[#f8fafd] transition-colors';
                div.innerHTML = `
                    <div class="flex items-start gap-3">
                        <i class="fas fa-map-marker-alt text-[#1f2a3f] mt-1 text-sm"></i>
                        <div class="flex-1">
                            <p class="text-sm font-medium text-[#1f2a3f]">${streetName}</p>
                            <p class="text-xs text-[#6f7c91] mt-0.5">
                                <span>${city}</span>
                                ${state ? ' &middot; ' + state : ''}
                            </p>
                            <p class="text-[10px] text-[#6f7c91] mt-0.5 font-mono">
                                ${badge}
                            </p>
                        </div>
                    </div>
                `;
                
                div.setAttribute('data-address', JSON.stringify(item));
                div.addEventListener('click', function() {
                    selectAddress(item);
                });
                
                suggestionsContainer.appendChild(div);
            });
            
            currentFocus = -1;
        }
        
        // --- 1. Maiaddy Engine ---
        if (MAIADDY_KEY) {
            console.log(`📡 [API Call]: Initiating Maiaddy search for: "${query}"`);
            fetch(`https://base-api.maiaddy.com/api/v1/addresses/search/street?streetName=${encodeURIComponent(query)}`, {
                method: 'GET',
                signal: maiaddyController.signal,
                headers: {
                    'Authorization': `Bearer ${MAIADDY_KEY.replace('Bearer ', '')}`,
                    'Accept': 'application/json',
                    'Content-Type': 'application/json'
                }
            })
            .then(response => {
                if (!response.ok) throw new Error(`HTTP error ${response.status}`);
                return response.json();
            })
            .then(data => {
                let rawList = [];
                if (data && data.streetName) {
                    rawList = [data];
                } else if (Array.isArray(data)) {
                    rawList = data;
                }
                maiaddyResults = rawList.map(r => ({ ...r, _source: 'maiaddy' }));
            })
            .catch(error => {
                if (error.name === 'AbortError') return;
                console.error(`❌ [API Error]: Maiaddy failed execution ->`, error.message);
            })
            .finally(() => {
                maiaddyDone = true;
                renderAllResults();
            });
        } else {
            maiaddyDone = true;
        }
        
        // --- 2. LocationIQ Engine ---
        if (LOCATIONIQ_KEY) {
            console.log(`📡 [API Call]: Initiating LocationIQ search for: "${query}"`);
            fetch(`https://api.locationiq.com/v1/autocomplete?key=${LOCATIONIQ_KEY}&q=${encodeURIComponent(query)}&limit=5&countrycodes=ng&dedupe=1`, {
                signal: locationiqController.signal
            })
            .then(response => {
                if (response.status === 404) return [];
                if (!response.ok) throw new Error(`HTTP error ${response.status}`);
                return response.json();
            })
            .then(data => {
                locationiqResults = (Array.isArray(data) ? data : []).map(r => ({ ...r, _source: 'locationiq' }));
            })
            .catch(error => {
                if (error.name === 'AbortError') return; 
                console.error(`❌ [API Error]: LocationIQ failed execution ->`, error.message);
            })
            .finally(() => {
                locationiqDone = true;
                renderAllResults();
            });
        } else {
            locationiqDone = true;
        }
        
        // --- 3. Geoapify Engine ---
        if (GEOAPIFY_KEY) {
            console.log(`📡 [API Call]: Initiating Geoapify search for: "${query}"`);
            fetch(`https://api.geoapify.com/v1/geocode/autocomplete?text=${encodeURIComponent(query)}&apiKey=${GEOAPIFY_KEY}&filter=countrycode:ng&limit=5`, {
                signal: geoapifyController.signal
            })
            .then(response => {
                if (!response.ok) throw new Error(`HTTP error ${response.status}`);
                return response.json();
            })
            .then(data => {
                const features = (data && Array.isArray(data.features)) ? data.features : [];
                geoapifyResults = features.map(f => ({ ...f, _source: 'geoapify' }));
            })
            .catch(error => {
                if (error.name === 'AbortError') return;
                console.error(`❌ [API Error]: Geoapify failed execution ->`, error.message);
            })
            .finally(() => {
                geoapifyDone = true;
                renderAllResults();
            });
        } else {
            geoapifyDone = true;
            renderAllResults();
        }
    }
    
    function selectAddress(item) {
        const source = item._source;
        let fullAddress = '';
        
        if (source === 'maiaddy') {
            const parts = [item.streetName, item.lga, item.state].filter(Boolean);
            fullAddress = parts.join(', ');
        } else if (source === 'locationiq') {
            fullAddress = item.display_name || '';
        } else if (source === 'geoapify') {
            fullAddress = item.properties?.formatted || '';
        }
        
        input.value = fullAddress;
        
        const alpineRoot = document.querySelector('[x-data]');
        if (alpineRoot && alpineRoot.__x && alpineRoot.__x.deliveryInfo) {
            alpineRoot.__x.deliveryInfo.address = fullAddress;
        }
        
        suggestionsContainer.classList.add('hidden');
        suggestionsContainer.innerHTML = '';
        
        console.log('🎯 [Address Selected]: Input populated.', {
            full_address: fullAddress,
            source: source
        });
    }
    
    function handleKeydown(e) {
        const items = suggestionsContainer.querySelectorAll('div[data-address]');
        if (!items.length) return;

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            currentFocus++;
            if (currentFocus >= items.length) currentFocus = 0;
            highlightItem(items);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            e.stopPropagation();
            currentFocus--;
            if (currentFocus < 0) currentFocus = items.length - 1;
            highlightItem(items);
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (currentFocus > -1 && items[currentFocus]) {
                const addressData = JSON.parse(items[currentFocus].getAttribute('data-address'));
                selectAddress(addressData);
            }
        } else if (e.key === 'Escape') {
            suggestionsContainer.classList.add('hidden');
            suggestionsContainer.innerHTML = '';
            currentFocus = -1;
        }
    }
    
    function highlightItem(items) {
        items.forEach(function(item, index) {
            if (index === currentFocus) {
                item.classList.add('bg-[#f8fafd]');
                item.scrollIntoView({ block: 'nearest' });
            } else {
                item.classList.remove('bg-[#f8fafd]');
            }
        });
    }
    
    document.addEventListener('click', function(e) {
        if (!input || !suggestionsContainer) return;
        if (!input.contains(e.target) && !suggestionsContainer.contains(e.target)) {
            suggestionsContainer.classList.add('hidden');
            suggestionsContainer.innerHTML = '';
            currentFocus = -1;
        }
    });
})();






// (function() {
//     const MAIADDY_KEY = window.MAIADDY_TOKEN;
//     const LOCATIONIQ_KEY = window.LOCATIONIQ_TOKEN;
    
//     if (!MAIADDY_KEY && !LOCATIONIQ_KEY) {
//         console.error('🚀 [Autocomplete API]: No address API tokens found on window object.');
//         return;
//     }
    
//     let debounceTimer = null;
//     let currentFocus = -1;
//     let input = null;
//     let suggestionsContainer = null;
    
//     let maiaddyController = null;
//     let locationiqController = null;
    
//     function initAutocomplete() {
//         input = document.getElementById('address-autocomplete');
//         suggestionsContainer = document.getElementById('address-suggestions');
        
//         if (!input || !suggestionsContainer) {
//             console.log('🚀 [Autocomplete]: elements not yet in DOM, waiting...');
//             return false;
//         }
        
//         input.removeEventListener('input', handleInput);
//         input.removeEventListener('keydown', handleKeydown);
        
//         input.addEventListener('input', handleInput);
//         input.addEventListener('keydown', handleKeydown);
        
//         console.log('🚀 [Autocomplete]: Initialized successfully (Maiaddy + LocationIQ fallback enabled)');
//         return true;
//     }
    
//     const observer = new MutationObserver(function() {
//         if (!input || !document.body.contains(input)) {
//             initAutocomplete();
//         }
//     });
//     observer.observe(document.body, { childList: true, subtree: true });
//     initAutocomplete();
    
//     function handleInput(e) {
//         const query = e.target.value.trim();
//         clearTimeout(debounceTimer);
        
//         if (query.length < 3) {
//             suggestionsContainer.classList.add('hidden');
//             suggestionsContainer.innerHTML = '';
//             return;
//         }
        
//         debounceTimer = setTimeout(function() {
//             fetchSuggestions(query);
//         }, 500);
//     }
    
//     function fetchSuggestions(query) {
//         if (maiaddyController) maiaddyController.abort();
//         if (locationiqController) locationiqController.abort();
        
//         maiaddyController = new AbortController();
//         locationiqController = new AbortController();
        
//         suggestionsContainer.innerHTML = `
//             <div class="px-4 py-3 text-sm text-[#6f7c91]">
//                 <i class="fas fa-spinner fa-pulse mr-2"></i>Searching addresses...
//             </div>
//         `;
//         suggestionsContainer.classList.remove('hidden');
        
//         let maiaddyDone = false;
//         let locationiqDone = false;
//         let allResults = [];
//         let maiaddyResults = [];
//         let locationiqResults = [];
        
//         function renderAllResults() {
//             console.log(`📊 [Autocomplete UI]: Merging results. Maiaddy count: ${maiaddyResults.length} | LocationIQ count: ${locationiqResults.length}`);
            
//             const combinedResults = [...maiaddyResults];
//             const maiaddyStreets = new Set(maiaddyResults.map(r => (r.streetName || '').toLowerCase().trim()));
            
//             locationiqResults.forEach(function(item) {
//                 const streetName = (item.address?.road || item.address?.pedestrian || item.display_name?.split(',')[0] || '').toLowerCase().trim();
//                 if (streetName && !maiaddyStreets.has(streetName)) {
//                     combinedResults.push(item);
//                 }
//             });
            
//             allResults = combinedResults;
//             console.log(`✨ [Autocomplete UI]: Total unique combined addresses to render: ${allResults.length}`);
            
//             if (allResults.length === 0) {
//                 suggestionsContainer.innerHTML = `
//                     <div class="px-4 py-3 text-sm text-[#6f7c91]">
//                         <i class="fas fa-search mr-2"></i>No addresses found. Try a different search.
//                     </div>
//                 `;
//                 return;
//             }
            
//             suggestionsContainer.innerHTML = '';
            
//             allResults.forEach(function(item, index) {
//                 const isMaiaddy = item._source === 'maiaddy';
//                 const streetName = isMaiaddy 
//                     ? (item.streetName || '')
//                     : (item.address?.road || item.address?.pedestrian || item.display_name?.split(',')[0] || '');
//                 const city = isMaiaddy 
//                     ? (item.lga || '')
//                     : (item.address?.city || item.address?.town || item.address?.village || '');
//                 const state = isMaiaddy 
//                     ? (item.state || '')
//                     : (item.address?.state || '');
                
//                 const div = document.createElement('div');
//                 div.className = 'px-4 py-3 cursor-pointer border-b border-[#f0f4fa] last:border-0 hover:bg-[#f8fafd] transition-colors';
//                 div.innerHTML = `
//                     <div class="flex items-start gap-3">
//                         <i class="fas fa-map-marker-alt text-[#1f2a3f] mt-1 text-sm"></i>
//                         <div class="flex-1">
//                             <p class="text-sm font-medium text-[#1f2a3f]">${streetName}</p>
//                             <p class="text-xs text-[#6f7c91] mt-0.5">
//                                 <span>${city}</span>
//                                 ${state ? ' &middot; ' + state : ''}
//                             </p>
//                             <p class="text-[10px] text-[#6f7c91] mt-0.5 font-mono">
//                                 ${isMaiaddy ? '📍 Maiaddy' : '🌍 LocationIQ'}
//                             </p>
//                         </div>
//                     </div>
//                 `;
                
//                 div.setAttribute('data-address', JSON.stringify(item));
//                 div.addEventListener('click', function() {
//                     selectAddress(item);
//                 });
                
//                 suggestionsContainer.appendChild(div);
//             });
            
//             currentFocus = -1;
//         }
        
//         // --- 1. Maiaddy Call (Nigeria Engine) ---
//         if (MAIADDY_KEY) {
//             console.log(`📡 [API Call]: Initiating Maiaddy search for: "${query}"`);
//             fetch(`https://base-api.maiaddy.com/api/v1/addresses/search/street?streetName=${encodeURIComponent(query)}`, {
//                 method: 'GET',
//                 signal: maiaddyController.signal,
//                 headers: {
//                     'Authorization': `Bearer ${MAIADDY_KEY.replace('Bearer ', '')}`,
//                     'Accept': 'application/json',
//                     'Content-Type': 'application/json'
//                 }
//             })
//             .then(response => {
//                 if (!response.ok) throw new Error(`HTTP error ${response.status}`);
//                 return response.json();
//             })
//             .then(data => {
//                 // FIXED: Maiaddy returns a flat dictionary structure on match, wrap it into an array
//                 let rawList = [];
//                 if (data && data.streetName) {
//                     rawList = [data];
//                 } else if (Array.isArray(data)) {
//                     rawList = data;
//                 }
                
//                 maiaddyResults = rawList.map(r => ({ ...r, _source: 'maiaddy' }));
//                 console.log(`✅ [API Success]: Maiaddy mapped ${maiaddyResults.length} records.`);
//             })
//             .catch(error => {
//                 if (error.name === 'AbortError') return;
//                 console.error(`❌ [API Error]: Maiaddy failed execution ->`, error.message);
//             })
//             .finally(() => {
//                 maiaddyDone = true;
//                 if (locationiqDone || !LOCATIONIQ_KEY) renderAllResults();
//             });
//         } else {
//             console.warn('⚠️ [API Skip]: Maiaddy token missing. Skipping call.');
//             maiaddyDone = true;
//         }
        
//         // --- 2. LocationIQ Call (Global Fallback) ---
//         if (LOCATIONIQ_KEY) {
//             console.log(`📡 [API Call]: Initiating LocationIQ autocomplete search for: "${query}"`);
//             fetch(`https://api.locationiq.com/v1/autocomplete?key=${LOCATIONIQ_KEY}&q=${encodeURIComponent(query)}&limit=5&countrycodes=ng&dedupe=1`, {
//                 signal: locationiqController.signal
//             })
//             .then(response => {
//                 if (response.status === 404) {
//                     console.log(`ℹ️ [API Info]: LocationIQ returned 404 (No matches found)`);
//                     return [];
//                 }
//                 if (!response.ok) throw new Error(`HTTP error ${response.status}`);
//                 return response.json();
//             })
//             .then(data => {
//                 locationiqResults = (Array.isArray(data) ? data : []).map(r => ({ ...r, _source: 'locationiq' }));
//                 console.log(`✅ [API Success]: LocationIQ returned ${locationiqResults.length} records.`);
//             })
//             .catch(error => {
//                 if (error.name === 'AbortError') return; 
//                 console.error(`❌ [API Error]: LocationIQ failed execution ->`, error.message);
//             })
//             .finally(() => {
//                 locationiqDone = true;
//                 if (maiaddyDone) renderAllResults();
//             });
//         } else {
//             console.warn('⚠️ [API Skip]: LocationIQ token missing. Skipping call.');
//             locationiqDone = true;
//             if (maiaddyDone) renderAllResults();
//         }
//     }
    
//     function selectAddress(item) {
//         const isMaiaddy = item._source === 'maiaddy';
//         let fullAddress = '';
        
//         if (isMaiaddy) {
//             const parts = [item.streetName, item.lga, item.state].filter(Boolean);
//             fullAddress = parts.join(', ');
//         } else {
//             fullAddress = item.display_name || '';
//         }
        
//         input.value = fullAddress;
        
//         const alpineRoot = document.querySelector('[x-data]');
//         if (alpineRoot && alpineRoot.__x && alpineRoot.__x.deliveryInfo) {
//             alpineRoot.__x.deliveryInfo.address = fullAddress;
//         }
        
//         suggestionsContainer.classList.add('hidden');
//         suggestionsContainer.innerHTML = '';
        
//         console.log('🎯 [Address Selected]: Input populated.', {
//             full_address: fullAddress,
//             source: item._source
//         });
//     }
    
//     function handleKeydown(e) {
//         const items = suggestionsContainer.querySelectorAll('div[data-address]');
//         if (!items.length) return;

//         if (e.key === 'ArrowDown') {
//             e.preventDefault();
//             currentFocus++;
//             if (currentFocus >= items.length) currentFocus = 0;
//             highlightItem(items);
//         } else if (e.key === 'ArrowUp') {
//             e.preventDefault();
//             e.stopPropagation();
//             currentFocus--;
//             if (currentFocus < 0) currentFocus = items.length - 1;
//             highlightItem(items);
//         } else if (e.key === 'Enter') {
//             e.preventDefault();
//             if (currentFocus > -1 && items[currentFocus]) {
//                 const addressData = JSON.parse(items[currentFocus].getAttribute('data-address'));
//                 selectAddress(addressData);
//             }
//         } else if (e.key === 'Escape') {
//             suggestionsContainer.classList.add('hidden');
//             suggestionsContainer.innerHTML = '';
//             currentFocus = -1;
//         }
//     }
    
//     function highlightItem(items) {
//         items.forEach(function(item, index) {
//             if (index === currentFocus) {
//                 item.classList.add('bg-[#f8fafd]');
//                 item.scrollIntoView({ block: 'nearest' });
//             } else {
//                 item.classList.remove('bg-[#f8fafd]');
//             }
//         });
//     }
    
//     document.addEventListener('click', function(e) {
//         if (!input || !suggestionsContainer) return;
//         if (!input.contains(e.target) && !suggestionsContainer.contains(e.target)) {
//             suggestionsContainer.classList.add('hidden');
//             suggestionsContainer.innerHTML = '';
//             currentFocus = -1;
//         }
//     });
// })();


// (function() {
//     const MAIADDY_KEY = window.MAIADDY_TOKEN;
//     const LOCATIONIQ_KEY = window.LOCATIONIQ_TOKEN;
    
//     if (!MAIADDY_KEY && !LOCATIONIQ_KEY) {
//         console.error('No address API tokens found');
//         return;
//     }
    
//     let debounceTimer = null;
//     let currentFocus = -1;
//     let input = null;
//     let suggestionsContainer = null;
    
//     function initAutocomplete() {
//         input = document.getElementById('address-autocomplete');
//         suggestionsContainer = document.getElementById('address-suggestions');
        
//         if (!input || !suggestionsContainer) {
//             console.log('Autocomplete: elements not yet in DOM, waiting...');
//             return false;
//         }
        
//         input.removeEventListener('input', handleInput);
//         input.removeEventListener('keydown', handleKeydown);
        
//         input.addEventListener('input', handleInput);
//         input.addEventListener('keydown', handleKeydown);
        
//         console.log('Autocomplete: initialized (Maiaddy + LocationIQ fallback)');
//         return true;
//     }
    
//     const observer = new MutationObserver(function() {
//         if (!input || !document.body.contains(input)) {
//             initAutocomplete();
//         }
//     });
//     observer.observe(document.body, { childList: true, subtree: true });
//     initAutocomplete();
    
//     function handleInput(e) {
//         const query = e.target.value.trim();
//         clearTimeout(debounceTimer);
        
//         if (query.length < 3) {
//             suggestionsContainer.classList.add('hidden');
//             suggestionsContainer.innerHTML = '';
//             return;
//         }
        
//         debounceTimer = setTimeout(function() {
//             fetchSuggestions(query);
//         }, 400);
//     }
    
//     function fetchSuggestions(query) {
//         suggestionsContainer.innerHTML = `
//             <div class="px-4 py-3 text-sm text-[#6f7c91]">
//                 <i class="fas fa-spinner fa-pulse mr-2"></i>Searching addresses...
//             </div>
//         `;
//         suggestionsContainer.classList.remove('hidden');
        
//         // Track which API responded and with what
//         let maiaddyDone = false;
//         let locationiqDone = false;
//         let allResults = [];
//         let maiaddyResults = [];
//         let locationiqResults = [];
        
//         function renderAllResults() {
//             // Combine: Maiaddy results first, then LocationIQ (deduplicated roughly)
//             const combinedResults = [...maiaddyResults];
//             const maiaddyStreets = new Set(maiaddyResults.map(r => r.streetName?.toLowerCase()));
            
//             locationiqResults.forEach(function(item) {
//                 const streetName = (item.address?.road || item.address?.pedestrian || item.display_name?.split(',')[0] || '').toLowerCase();
//                 if (!maiaddyStreets.has(streetName)) {
//                     combinedResults.push(item);
//                 }
//             });
            
//             allResults = combinedResults;
            
//             if (allResults.length === 0) {
//                 suggestionsContainer.innerHTML = `
//                     <div class="px-4 py-3 text-sm text-[#6f7c91]">
//                         <i class="fas fa-search mr-2"></i>No addresses found. Try a different search.
//                     </div>
//                 `;
//                 return;
//             }
            
//             suggestionsContainer.innerHTML = '';
            
//             allResults.forEach(function(item, index) {
//                 const isMaiaddy = item._source === 'maiaddy';
//                 const streetName = isMaiaddy 
//                     ? (item.streetName || '')
//                     : (item.address?.road || item.address?.pedestrian || item.display_name?.split(',')[0] || '');
//                 const city = isMaiaddy 
//                     ? (item.lga || '')
//                     : (item.address?.city || item.address?.town || item.address?.village || '');
//                 const state = isMaiaddy 
//                     ? (item.state || '')
//                     : (item.address?.state || '');
                
//                 const div = document.createElement('div');
//                 div.className = 'px-4 py-3 cursor-pointer border-b border-[#f0f4fa] last:border-0 hover:bg-[#f8fafd] transition-colors';
//                 div.innerHTML = `
//                     <div class="flex items-start gap-3">
//                         <i class="fas fa-map-marker-alt text-[#1f2a3f] mt-1 text-sm"></i>
//                         <div class="flex-1">
//                             <p class="text-sm font-medium text-[#1f2a3f]">${streetName}</p>
//                             <p class="text-xs text-[#6f7c91] mt-0.5">
//                                 <span>${city}</span>
//                                 ${state ? ' &middot; ' + state : ''}
//                             </p>
//                             <p class="text-[10px] text-[#6f7c91] mt-0.5 font-mono">
//                                 ${isMaiaddy ? '📍 Maiaddy' : '🌍 LocationIQ'}
//                             </p>
//                         </div>
//                     </div>
//                 `;
                
//                 div.setAttribute('data-address', JSON.stringify(item));
                
//                 div.addEventListener('click', function() {
//                     selectAddress(item);
//                 });
                
//                 suggestionsContainer.appendChild(div);
//             });
            
//             currentFocus = -1;
//         }
        
//         // Try Maiaddy first (Nigeria-optimized)
//         if (MAIADDY_KEY) {
//             fetch(`https://base-api.maiaddy.com/api/v1/addresses/search/street?streetName=${encodeURIComponent(query)}`, {
//                 headers: {
//                     'Authorization': `Bearer ${MAIADDY_KEY}`,
//                     'Content-Type': 'application/json'
//                 }
//             })
//             .then(response => {
//                 if (!response.ok) throw new Error('Maiaddy error');
//                 return response.json();
//             })
//             .then(data => {
//                 const results = Array.isArray(data) ? data : (data && data.loccode ? [data] : []);
//                 maiaddyResults = results.map(r => ({ ...r, _source: 'maiaddy' }));
//                 maiaddyDone = true;
//                 if (locationiqDone || !LOCATIONIQ_KEY) renderAllResults();
//             })
//             .catch(function(error) {
//                 console.warn('Maiaddy failed, waiting for LocationIQ fallback:', error.message);
//                 maiaddyDone = true;
//                 if (locationiqDone || !LOCATIONIQ_KEY) renderAllResults();
//             });
//         } else {
//             maiaddyDone = true;
//         }
        
//         // Fallback: LocationIQ
//         if (LOCATIONIQ_KEY) {
//             // fetch(`https://api.locationiq.com/v1/autocomplete?key=${LOCATIONIQ_KEY}&q=${encodeURIComponent(query)}&limit=5&countrycodes=ng&dedupe=1`)
//             fetch(`https://api.locationiq.com/v1/autocomplete.php?key=${LOCATIONIQ_KEY}&q=${encodeURIComponent(query)}&limit=5&countrycodes=ng&dedupe=1`)
//             .then(response => {
//                 if (!response.ok) throw new Error('LocationIQ error');
//                 return response.json();
//             })
//             .then(data => {
//                 locationiqResults = (data || []).map(r => ({ ...r, _source: 'locationiq' }));
//                 locationiqDone = true;
//                 if (maiaddyDone) renderAllResults();
//             })
//             .catch(function(error) {
//                 console.warn('LocationIQ failed:', error.message);
//                 locationiqDone = true;
//                 if (maiaddyDone) renderAllResults();
//             });
//         } else {
//             locationiqDone = true;
//         }
//     }
    
//     function selectAddress(item) {
//         const isMaiaddy = item._source === 'maiaddy';
//         let fullAddress = '';
        
//         if (isMaiaddy) {
//             const parts = [item.streetName, item.lga, item.state].filter(Boolean);
//             fullAddress = parts.join(', ');
//         } else {
//             fullAddress = item.display_name || '';
//         }
        
//         input.value = fullAddress;
        
//         const alpineRoot = document.querySelector('[x-data]');
//         if (alpineRoot && alpineRoot.__x) {
//             alpineRoot.__x.deliveryInfo.address = fullAddress;
//         }
        
//         suggestionsContainer.classList.add('hidden');
//         suggestionsContainer.innerHTML = '';
        
//         console.log('Selected address:', {
//             full_address: fullAddress,
//             source: item._source
//         });
//     }
    
//     // --- Keyboard navigation (unchanged from before) ---
//     function handleKeydown(e) {
//         const items = suggestionsContainer.querySelectorAll('div[data-address]');
//         if (e.key === 'ArrowDown') {
//             e.preventDefault();
//             currentFocus++;
//             if (currentFocus >= items.length) currentFocus = 0;
//             highlightItem(items);
//         } else if (e.key === 'ArrowUp') {
//             e.preventDefault();
//             currentFocus--;
//             if (currentFocus < 0) currentFocus = items.length - 1;
//             highlightItem(items);
//         } else if (e.key === 'Enter') {
//             e.preventDefault();
//             if (currentFocus > -1 && items[currentFocus]) {
//                 const addressData = JSON.parse(items[currentFocus].getAttribute('data-address'));
//                 selectAddress(addressData);
//             }
//         } else if (e.key === 'Escape') {
//             suggestionsContainer.classList.add('hidden');
//             suggestionsContainer.innerHTML = '';
//             currentFocus = -1;
//         }
//     }
    
//     function highlightItem(items) {
//         items.forEach(function(item, index) {
//             if (index === currentFocus) {
//                 item.classList.add('bg-[#f8fafd]');
//                 item.scrollIntoView({ block: 'nearest' });
//             } else {
//                 item.classList.remove('bg-[#f8fafd]');
//             }
//         });
//     }
    
//     document.addEventListener('click', function(e) {
//         if (!input || !suggestionsContainer) return;
//         if (!input.contains(e.target) && !suggestionsContainer.contains(e.target)) {
//             suggestionsContainer.classList.add('hidden');
//             suggestionsContainer.innerHTML = '';
//             currentFocus = -1;
//         }
//     });
// })();