(function() {
    
    // Check if your script file loaded
    console.log('Locationiq Script loaded check');
    const input = document.getElementById('address-autocomplete');
    const suggestionsContainer = document.getElementById('address-suggestions');
    let debounceTimer = null;
    let currentFocus = -1;
    
    // Replace with your actual LocationIQ API key
    const LOCATIONIQ_KEY = window.LOCATIONIQ_TOKEN || 'YOUR_LOCATIONIQ_KEY_HERE';
    
    if (!LOCATIONIQ_KEY) {
        console.error('LocationIQ token not found');
        return;
    }
    if (!input || !suggestionsContainer) return;
    
    input.addEventListener('input', function(e) {
        const query = this.value.trim();
        
        // Clear any pending debounce
        clearTimeout(debounceTimer);
        
        // Hide suggestions if query is too short
        if (query.length < 3) {
            suggestionsContainer.classList.add('hidden');
            suggestionsContainer.innerHTML = '';
            return;
        }
        
        // Debounce: wait 400ms after user stops typing (that's about every 5 keystrokes)
        debounceTimer = setTimeout(function() {
            fetchSuggestions(query);
        }, 400);
    });
    
    function fetchSuggestions(query) {
        // Show loading state
        suggestionsContainer.innerHTML = `
            <div class="px-4 py-3 text-sm text-[#6f7c91]">
                <i class="fas fa-spinner fa-pulse mr-2"></i>Searching...
            </div>
        `;
        suggestionsContainer.classList.remove('hidden');
        
        fetch(`https://api.locationiq.com/v1/autocomplete?key=${LOCATIONIQ_KEY}&q=${encodeURIComponent(query)}&limit=5&countrycodes=ng&dedupe=1`)
            .then(response => {
                if (!response.ok) throw new Error('API error');
                return response.json();
            })
            .then(data => {
                if (!data || data.length === 0) {
                    suggestionsContainer.innerHTML = `
                        <div class="px-4 py-3 text-sm text-[#6f7c91]">
                            <i class="fas fa-search mr-2"></i>No addresses found
                        </div>
                    `;
                    return;
                }
                
                suggestionsContainer.innerHTML = '';
                data.forEach(function(item, index) {
                    const div = document.createElement('div');
                    div.className = 'px-4 py-3 cursor-pointer border-b border-[#f0f4fa] last:border-0 hover:bg-[#f8fafd] transition-colors';
                    div.innerHTML = `
                        <div class="flex items-start gap-3">
                            <i class="fas fa-map-marker-alt text-[#1f2a3f] mt-1 text-sm"></i>
                            <div class="flex-1">
                                <p class="text-sm font-medium text-[#1f2a3f]">${item.display_name}</p>
                                <p class="text-xs text-[#6f7c91] mt-0.5">
                                    <span class="capitalize">${item.address.city || item.address.town || item.address.village || ''}</span>
                                    ${item.address.state ? ', ' + item.address.state : ''}
                                    ${item.address.country ? ', ' + item.address.country : ''}
                                </p>
                            </div>
                        </div>
                    `;
                    
                    // Store the full address data
                    div.setAttribute('data-address', JSON.stringify(item));
                    
                    div.addEventListener('click', function() {
                        selectAddress(item);
                    });
                    
                    suggestionsContainer.appendChild(div);
                });
                
                currentFocus = -1;
            })
            .catch(function(error) {
                console.error('LocationIQ error:', error);
                suggestionsContainer.innerHTML = `
                    <div class="px-4 py-3 text-sm text-red-500">
                        <i class="fas fa-exclamation-circle mr-2"></i>Error loading suggestions. Type address manually.
                    </div>
                `;
            });
    }
    
    function selectAddress(item) {
        // Populate the address field with the full display name
        input.value = item.display_name;
        
        // Also update the Alpine.js deliveryInfo model
        const alpineData = document.querySelector('[x-data]').__x;
        if (alpineData) {
            alpineData.deliveryInfo.address = item.display_name;
        }
        
        // Hide suggestions
        suggestionsContainer.classList.add('hidden');
        suggestionsContainer.innerHTML = '';
        
        // Log the structured data (city, state, country are in item.address)
        console.log('Selected address:', {
            full_address: item.display_name,
            city: item.address.city || item.address.town || item.address.village,
            state: item.address.state,
            country: item.address.country,
            postcode: item.address.postcode
        });
    }
    
    // Keyboard navigation
    input.addEventListener('keydown', function(e) {
        const items = suggestionsContainer.querySelectorAll('div[data-address]');
        
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            currentFocus++;
            if (currentFocus >= items.length) currentFocus = 0;
            highlightItem(items);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
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
    });
    
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
    
    // Close suggestions when clicking outside
    document.addEventListener('click', function(e) {
        if (!input.contains(e.target) && !suggestionsContainer.contains(e.target)) {
            suggestionsContainer.classList.add('hidden');
            suggestionsContainer.innerHTML = '';
            currentFocus = -1;
        }
    });
})();