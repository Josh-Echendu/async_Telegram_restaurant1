# handlers/order_handler.py - EXACT COPY FROM ORIGINAL FILE
from core.config import *
from utils.cart_utils import *
from utils.image_utils import *
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


EMOJI_NUMBERS = {
    1: "1️⃣", 2: "2️⃣", 3: "3️⃣",
    4: "4️⃣", 5: "5️⃣", 6: "6️⃣",
    7: "7️⃣", 8: "8️⃣", 9: "9️⃣",
    10: "🔟"
}

async def choose_table(update, query):

    user_session = await get_user_session(update.effective_user.id)
    max_tables = user_session['max_tables']

    keyboard = []
    row = []

    for i in range(1, max_tables + 1):
        emoji = EMOJI_NUMBERS.get(i, str(i))  # fallback to normal number

        button = InlineKeyboardButton(
            text=emoji,
            callback_data=f"table_{emoji}"
        )

        row.append(button)

        if len(row) == 3:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text="Select a table:",
        reply_markup=reply_markup
    )

async def order_meal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await logger(update, context)
    user_session = await get_user_session(update.effective_user.id)
    service_mode = user_session['service_mode'].lower()
    business_type = user_session['business_type'].lower()
    keyboard = []

    # 🟢 Vendor → always delivery only
    if business_type == "vendor":
        keyboard.append([
            InlineKeyboardButton("🚚 Delivery", callback_data="order_delivery")
        ])

    # 🟡 Restaurant
    else:
        row = []

        if service_mode.lower() in ["dine_in", "both"]:
            row.append(InlineKeyboardButton("🍽️ Dine-in", callback_data="order_dine_in"))

        if service_mode.lower() in ["delivery", "both"]:
            row.append(InlineKeyboardButton("🚚 Delivery", callback_data="order_delivery"))

        keyboard.append(row)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="How would you like to order?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
        
                                                
# <!DOCTYPE html>
# <html lang="en">
# <head>
#   <meta charset="UTF-8">
#   <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes">
#   <title>FORK & CO. · premium eats</title>
#   <!-- Tailwind via CDN + custom layer -->
#   <script src="https://cdn.tailwindcss.com"></script>
#   <!-- <script src="https://cdn.jsdelivr.net/npm/axios/dist/axios.min.js"></script> -->
#   <script src="https://telegram.org/js/telegram-web-app.js"></script>
#   {% csrf_token %}
#   <script src="https://cdn.jsdelivr.net/npm/axios/dist/axios.min.js"></script>

#   <script>
#       const tg = window.Telegram.WebApp;

#       const user = tg.initDataUnsafe.user;

#       console.log(user.first_name);
#       console.log(user.id);
#       tg.sendData("hello");

#       tg.ready();
#   </script>

#   <script>
#     function getCSRFToken() {
#         return document.cookie
#             .split('; ')
#             .find(row => row.startsWith('csrftoken='))
#             ?.split('=')[1];
#     }

#     axios.defaults.headers.common['X-CSRFToken'] = getCSRFToken();
#   </script>
#   <!-- Alpine.js (lightweight magic) -->
#   <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
#   <!-- Font Awesome 6 (free icons) -->
#   <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
#   <!-- smooth animations with tiny gsap? we use pure css but add a touch of class -->
#   <style>
#     /* import modern bright fonts: inter + italic luxury accent */
#     @import url('https://fonts.googleapis.com/css2?family=Inter:ital,opsz,wght@0,14..32,100..900;1,14..32,100..900&family=Quicksand:wght@300..700&display=swap');
    
#     * {
#       margin: 0;
#       padding: 0;
#       box-sizing: border-box;
#     }
    
#     body {
#       font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
#       background: #ffffff;  /* bright clean base like Temu/Shopify */
#       color: #1a1e2b;
#     }
    
#     /* elegant white-italic headings */
#     .brand-italic {
#       font-family: 'Quicksand', sans-serif;
#       font-weight: 600;
#       font-style: italic;
#       letter-spacing: -0.02em;
#       background: linear-gradient(135deg, #2d3648 0%, #121725 100%);
#       -webkit-background-clip: text;
#       -webkit-text-fill-color: transparent;
#       background-clip: text;
#     }
    
#     /* card design : bright, airy, shadows soft */
#     .meal-card {
#       background: #ffffff;
#       border-radius: 28px;
#       box-shadow: 0 12px 30px -8px rgba(0, 20, 30, 0.08), 0 4px 8px -2px rgba(0, 0, 0, 0.02);
#       transition: all 0.25s ease;
#       border: 1px solid rgba(230, 240, 255, 0.5);
#     }
    
#     .meal-card:hover {
#       transform: translateY(-3px);
#       box-shadow: 0 24px 40px -12px rgba(0, 100, 150, 0.18);
#       border-color: rgba(180, 210, 255, 0.5);
#     }
    
#     /* category pills (bright, modern) */
#     .cat-pill {
#       background: #ffffff;
#       border: 1px solid #eef2f8;
#       color: #334155;
#       font-weight: 500;
#       padding: 0.65rem 1.5rem;
#       border-radius: 60px;
#       box-shadow: 0 4px 12px -6px rgba(0,0,0,0.02);
#       transition: 0.15s;
#       white-space: nowrap;
#       backdrop-filter: blur(4px);
#     }
    
#     .cat-pill.active {
#       background: #1f2a3f;
#       border-color: #1f2a3f;
#       color: white;
#       font-weight: 500;
#       box-shadow: 0 10px 20px -10px #1f2a3f80;
#     }
    
#     /* sticky header clean */
#     .sticky-bright {
#       backdrop-filter: blur(18px) saturate(180%);
#       background: rgba(255, 255, 255, 0.75);
#       border-bottom: 1px solid rgba(220, 230, 245, 0.7);
#     }
    
#     /* quantity button modern */
#     .qty-btn {
#       background: white;
#       border: 1px solid #dee7f2;
#       color: #1f2a3f;
#       width: 36px;
#       height: 36px;
#       border-radius: 40px;
#       display: inline-flex;
#       align-items: center;
#       justify-content: center;
#       font-weight: 600;
#       transition: 0.15s;
#     }
    
#     .qty-btn:hover {
#       background: #1f2a3f;
#       border-color: #1f2a3f;
#       color: white;
#     }
    
#     /* cart drawer (right side bright) */
#     .cart-drawer-bright {
#       background: rgba(255, 255, 255, 0.98);
#       backdrop-filter: blur(14px);
#       border-left: 1px solid #e2eaf5;
#       box-shadow: -25px 0 50px -20px rgba(0,0,0,0.15);
#     }
    
#     /* toast */
#     .toast-shop {
#       background: #1f2a3f;
#       color: #ffffff;
#       border-radius: 60px;
#       box-shadow: 0 30px 45px -25px #1f2a3fcc, 0 0 0 1px rgba(255,255,255,0.1) inset;
#       font-weight: 500;
#       border: 1px solid #ffffff40;
#     }
    
#     /* floating micro-animation */
#     @keyframes gentle-pulse {
#       0% { opacity: 0.9; transform: scale(1); }
#       50% { opacity: 1; transform: scale(1.02); }
#       100% { opacity: 0.9; transform: scale(1); }
#     }
    
#     .badge-pulse {
#       animation: gentle-pulse 2s infinite;
#     }
    
#     /* scroll hidden for categories */
#     .no-scrollbar::-webkit-scrollbar {
#       display: none;
#     }
#     .no-scrollbar {
#       -ms-overflow-style: none;
#       scrollbar-width: none;
#     }
    
#     /* image wrapper */
#     .img-wrapper {
#       border-radius: 24px 24px 12px 12px;
#       overflow: hidden;
#       background: #f7f9fc;
#     }
    
#     .img-wrapper img {
#       transition: transform 0.4s ease;
#     }
#     .meal-card:hover .img-wrapper img {
#       transform: scale(1.05);
#     }
#   </style>
# </head>
# <body class="antialiased">

# <!-- ALPINE STORE (frontend mock) -->
# <div x-data="{
#   cart: [],
#   activeCategory: 'all',
#   showCart: false,
#   showCheckoutModal: false,
#   toast: { visible: false, message: '' },
#   orderId: 'ORD-' + Math.floor(800000 + Math.random()*200000),
  
#   // bright, aspirational menu (like Shopify frontpage)
#   meals: [],
#   allmeals: [],  // for 'all' category caching
#   currentPage: 1,
#   perPage: 3,

#   mapProducts(products, categoryOverride = null) {
#     return products.map(p => ({
#       pid: String(p.pid),
#       name: p.title,
#       desc: p.description || '',
#       price: parseFloat(p.price),
#       category: categoryOverride ?? String(p.category),
#       image: p.image,
#       in_stock: p.in_stock !== false
#     }));
#   },


#   async loadProducts(cid) {

#     try {

#       const pathParts = window.location.pathname.split('/').filter(p => p);
#       const restaurantId = pathParts[2];

#       const url = `/api/restaurant/${restaurantId}/products/${cid}/`;

#       const response = await axios.get(url);

#       console.log('API response:', response.data);

#       const categoryProducts = response.data.category_products;
#       const allProducts = response.data.all;

#       // Always update ALL meals cache
#       this.allmeals = this.mapProducts(allProducts);

#       // Update current visible meals
#       this.meals = this.mapProducts(
#         categoryProducts,
#         cid === 'all' ? null : String(cid)
#       );
#       console.log('Mapped meals:', this.meals);

#       // Sort current meals
#       this.meals.sort((a, b) => b.in_stock - a.in_stock);

#       // 🔥 IMPORTANT: validate cart against ALL products (not category only)
#       this.validateCart();

#     } catch (error) {

#       console.error('Failed to load products:', error);
#       this.meals = [];
#       }
#   },

  
#   categories: [],

#   async loadCategories() {
#     try {
#       const pathParts = window.location.pathname.split('/').filter(p => p);
#       const restaurantId = pathParts[2]; // this gives 'res533f34g214'
#       console.log('Loading categories for restaurant ID:', restaurantId);

#       const response = await axios.get(
#         `/api/restaurant/${restaurantId}/categories/`
#       );
#       console.log('Categories loaded:', response.data);

#       this.categories = [
#         { id: 'all', name: 'All' },
#         ...response.data.map(cat => ({
#           id: cat.cid,
#           name: cat.title
#         }))
#       ];

#     } catch (error) {
#       console.error('Failed to load categories:', error);
#     }
#   },

#   validateCart() {

#     this.cart = this.cart.map(cartItem => {

#       // search in ALL meals, not current category
#       const meal = this.allmeals.find(m => m.pid === cartItem.pid);

#       if (meal) {
#         return {
#           ...cartItem,
#           in_stock: meal.in_stock
#         };

#       }

#       return {
#         ...cartItem,
#         in_stock: false
#       };

#     });

#     localStorage.setItem('fork_cart', JSON.stringify(this.cart));

#     console.log('Cart validated against ALL meals:', this.cart);
#   },

#   get filteredMeals() {
#     if (this.activeCategory === 'all') return this.meals;
#       return this.meals.filter(m => String(m.category) === String(this.activeCategory));
#   },

#   get totalPages() {
#   return Math.ceil(this.filteredMeals.length / this.perPage);
#   },

#   get paginatedMeals() {
#     const start = (this.currentPage - 1) * this.perPage;
#     const end = start + this.perPage;
#     return this.filteredMeals.slice(start, end);
#   },
  
#   get cartCount() {
#     return this.cart.reduce((acc, i) => acc + i.quantity, 0);
#   },
  
#   get cartTotal() {
#     return this.cart.reduce((acc, i) => acc + (i.price * i.quantity), 0).toFixed(2);
#   },

#   saveCart() {
#     localStorage.setItem('fork_cart', JSON.stringify(this.cart));
#   },
  
#   addToCart(meal) {

#     // STOP if out of stock
#     if (!meal.in_stock) {

#       this.toast = {
#         visible: true,
#         message: 'This item is currently out of stock'
#       };

#       setTimeout(() => this.toast.visible = false, 2000);

#       return;
#     }

#     const found = this.cart.find(i => i.pid === meal.pid);

#     if (found) {
#         found.quantity++;
#     } else {
#         this.cart.push({ ...meal, pid: String(meal.pid), quantity: 1 });
#     }

#     this.saveCart();
#   },
  
#   removeOne(mealId) {
#     const idx = this.cart.findIndex(i => i.pid === mealId);

#     if (idx !== -1) {
#         if (this.cart[idx].quantity > 1) {
#             this.cart[idx].quantity--;
#         } else {
#             this.cart.splice(idx, 1);
#         }
#     }

#     this.saveCart();
#   },
  
#   clearCart() {
#     this.cart = [];
#     localStorage.removeItem('fork_cart');
#   },
  
#   placeOrder() {

#     // FIRST: block if out of stock exists
#     if (this.cart.some(item => !item.in_stock)) {

#       this.toast = {
#         visible: true,
#         message: 'Remove out-of-stock items before checkout'
#       };

#       setTimeout(() => this.toast.visible = false, 10000);

#       return;
#     }

#     // SECOND: block if cart empty
#     if (this.cart.length === 0) {

#       this.toast = {
#         visible: true,
#         message: '✨ Your cart is empty — add some delicious items!'
#       };

#       setTimeout(() => this.toast.visible = false, 2200);

#       return;
#     }

#     // THIRD: allow checkout
#     this.orderId = 'ORD-' + Math.floor(800000 + Math.random()*200000);
#     this.showCheckoutModal = true;
#   },

#   get hasOutOfStockItems() {
#     return this.cart.some(item => !item.in_stock);
#   },
  

#   async confirmOrder() {
#     try {

#         const pathParts = window.location.pathname.split('/').filter(p => p);
#         const restaurantId = pathParts[2]; // this gives 'res533f34g214'
#         console.log('Submitting order for restaurant ID:', restaurantId);

#         // Send order to backend
#         const response = await axios.post(`/api/order_batches/${restaurantId}/`, {
#             cart_items: this.cart.map(i => ({pid: i.pid, quantity: i.quantity})),
#             idempotency_key: 'ORD-' + Math.floor(800000 + Math.random() * 200000),
#             init_data: window.Telegram.WebApp.initData

#         });

#         const data = response.data;
#         console.log(data)


#         if (data.success) {
#             // ✅ Order fully successful
#             this.showCheckoutModal = false;
#             this.showCart = false;
#             this.clearCart();

#             this.toast = {
#                 visible: true,
#                 message: '🍽️ Your order was placed successfully! Check WhatsApp for details.'
#             };
#             setTimeout(() => this.toast.visible = false, 7200);
            

#         } else if (data.product_ids && data.product_ids.length > 0) {
#             // ⚠️ Some items out of stock
#             this.cart = this.cart.map(item => {
#                 if (data.product_ids.includes(item.pid)) {
#                     return { ...item, in_stock: false };
#                 }
#                 return item;
#             });

#             this.saveCart();
#             this.loadProducts(this.activeCategory);

#             // Keep cart open so user sees changes
#             this.showCheckoutModal = false;
#             this.showCart = true;

#             this.toast = {
#                 visible: true,
#                 message: '⚠️ Some items are out of stock and have been disabled in your cart.'
#             };
#             setTimeout(() => this.toast.visible = false, 10000);
#         }

#     } catch (error) {
#         console.error('Order submission failed:', error);
#         this.toast = {
#             visible: true,
#             message: '❌ Failed to place order. Please try again.'
#         };
#         setTimeout(() => this.toast.visible = false, 7000);
#     }
# }
# }"

# x-init="
#   activeCategory = 'all';

#   const saved = localStorage.getItem('fork_cart');

#   if (saved) {
#     try{
#       // REMOVE 'this.' - Alpine maps these directly to your data object
#       cart = JSON.parse(saved);
#     } catch(e) {
#       console.error('Failed to parse saved cart:', e);
#       cart = [];
#     }
#   }

#   loadCategories();
#   loadProducts('all');

# "
# class="max-w-7xl mx-auto px-4 sm:px-5 lg:px-6 pb-24 relative"
# >

# <!-- ===== HEADER (sticky, bright) ===== -->
# <header class="sticky top-0 z-40 sticky-bright py-3 sm:py-4 flex items-center justify-between rounded-2xl px-3">
#   <div class="flex items-center gap-2">
#     <i class="fas fa-utensils text-3xl text-[#1f2a3f]"></i>
#     <span class="text-2xl sm:text-3xl brand-italic font-bold">fork & co.</span>
#   </div>
#   <button @click="showCart = true" class="relative p-2.5 rounded-full bg-white shadow-sm border border-[#e9ecf2]">
#     <i class="fas fa-bag-shopping text-xl text-[#1f2a3f]"></i>
#     <span x-show="cartCount > 0" x-cloak class="absolute -top-1 -right-1 bg-[#1f2a3f] text-white text-xs font-bold px-1.5 py-0.5 rounded-full min-w-[20px] text-center">{{ cartCount }}</span>
#   </button>
# </header>

# <!-- ===== CATEGORY PILLS (horizontal scroll) ===== -->
# <div class="my-4 flex flex-wrap gap-2 pb-3 no-scrollbar md:justify-start">  <!-- Loop over all categories -->
#   <template x-for="cat in categories" :key="cat.id">
#     <button
#       type="button"
#       @click="
#         // Set the active category to the clicked category's id
#         activeCategory = cat.id;

#         // Reset page when category changes
#         currentPage = 1;

#         // Call the function to load products for this category
#         loadProducts(cat.id);
#       "
#       :class="
#         // Apply the 'active' class if this category is the active one
#         activeCategory === cat.id ? 'active' : ''
#       "
#       class="cat-pill text-sm sm:text-base transition-all duration-200"
#     >
#       <!-- Display the category name -->
#       <span x-text="cat.name"></span>
#     </button>
#   </template>
# </div>

# <!-- ===== MEALS GRID (beautiful cards) ===== -->
# <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5 sm:gap-6">
#   <template x-for="meal in paginatedMeals" :key="meal.pid">
#   <div
#     class="meal-card p-4 flex flex-col"
#     :class="!meal.in_stock ? 'opacity-50 pointer-events-none' : ''"
#   >      
#     <!-- image container -->
#      <div class="img-wrapper w-full h-44 sm:h-48 bg-[#f5f7fb] rounded-2xl relative">
#         <img :src="meal.image" :alt="meal.name" class="w-full h-full object-cover">
      
#         <!-- ADD THIS BADGE -->
#         <div
#           x-show="!meal.in_stock"
#           class="absolute top-3 left-3 bg-red-500 text-white text-xs font-bold px-3 py-1 rounded-full shadow">
#             Out of stock
#         </div>
#       </div>
      
#       <!-- text -->
#       <div class="mt-3 flex-1">
#         <h3 class="text-sm font-semibold text-[#1a1e2b]" x-text="meal.name"></h3>
#         <p class="text-sm text-[#4b5565] mt-0.5 line-clamp-2" x-text="meal.desc"></p>
        
#         <!-- price and action row -->
#         <div class="flex items-center justify-between mt-4">
#           <!-- dynamic if in cart -->
#           <template x-for="item in cart.filter(i => i.pid === meal.pid)" :key="item.pid">
#             <div class="flex items-center space-x-1 bg-[#f2f6fd] rounded-full border border-[#dee7f2] p-0.5">
#               <button @click="removeOne(meal.pid)" class="qty-btn w-8 h-8 text-sm"><i class="fas fa-minus"></i></button>
#               <span class="font-semibold w-6 text-center" x-text="item.quantity"></span>
#               <button @click="addToCart(meal)" class="qty-btn w-8 h-8 text-sm"><i class="fas fa-plus"></i></button>
#             </div>
#           </template>
          
#         <button
#           x-show="!cart.some(i => i.pid === meal.pid)"
#           @click="if(meal.in_stock) addToCart(meal)"
#           :class="meal.in_stock
#             ? 'bg-[#1f2a3f] hover:bg-[#2b384f] text-white'
#             : 'bg-gray-400 cursor-not-allowed text-white'"
#           class="px-5 py-2.5 rounded-full text-sm font-medium shadow-md flex items-center gap-1 transition-all"
#         >
#           <i class="fas fa-cart-plus"></i>
#           <span x-text="meal.in_stock ? 'Add' : 'Out of stock'"></span>
#         </button>
          
#           <span class="text-lg font-bold text-[#1f2a3f]" x-show="!cart.some(i => i.pid === meal.pid)">₦<span x-text="meal.price.toFixed(2)"></span></span>
#         </div>
#       </div>
#     </div>
#   </template>
# </div>

# <!-- ===== PREMIUM PAGINATION ===== -->
# <div 
#   x-show="totalPages > 1"
#   class="flex items-center justify-center mt-10 gap-2 select-none"
# >

#   <!-- Previous -->
#   <button
#     @click="if(currentPage > 1) currentPage--"
#     :class="currentPage === 1 
#       ? 'opacity-40 cursor-not-allowed' 
#       : 'hover:bg-[#1f2a3f] hover:text-white hover:scale-105'"
#     class="w-11 h-11 rounded-full border border-[#e2e8f0] bg-white shadow-sm transition-all duration-200 flex items-center justify-center"
#   >
#     <i class="fas fa-chevron-left text-sm"></i>
#   </button>

#   <!-- Page numbers -->
#   <template x-for="page in totalPages" :key="page">

#     <button
#       @click="currentPage = page"
#       x-text="page"
#       :class="
#         currentPage === page
#         ? 'bg-[#1f2a3f] text-white shadow-lg scale-110'
#         : 'bg-white text-[#1f2a3f] hover:bg-[#1f2a3f] hover:text-white hover:scale-105'
#       "
#       class="w-11 h-11 rounded-full border border-[#e2e8f0] font-semibold transition-all duration-200 shadow-sm"
#     ></button>

#   </template>

#   <!-- Next -->
#   <button
#     @click="if(currentPage < totalPages) currentPage++"
#     :class="currentPage === totalPages 
#       ? 'opacity-40 cursor-not-allowed' 
#       : 'hover:bg-[#1f2a3f] hover:text-white hover:scale-105'"
#     class="w-11 h-11 rounded-full border border-[#e2e8f0] bg-white shadow-sm transition-all duration-200 flex items-center justify-center"
#   >
#     <i class="fas fa-chevron-right text-sm"></i>
#   </button>

# </div>


# <!-- ===== CART DRAWER (bright, modal right) ===== -->
# <div x-show="showCart" class="fixed inset-0 z-50 flex justify-end" @keydown.escape.window="showCart = false">
#   <!-- backdrop -->
#   <div class="absolute inset-0 bg-black/5 backdrop-blur-[2px]" @click="showCart = false"></div>
  
#   <!-- drawer -->
#   <div class="relative w-full max-w-md cart-drawer-bright h-full shadow-xl flex flex-col"
#        x-show="showCart" x-transition:enter="transition ease-out duration-300" x-transition:enter-start="translate-x-full opacity-0" x-transition:enter-end="translate-x-0 opacity-100" x-transition:leave="transition ease-in duration-200" x-transition:leave-start="translate-x-0 opacity-100" x-transition:leave-end="translate-x-full opacity-0">
    
#     <div class="flex items-center justify-between p-5 border-b border-[#eef2f8]">
#       <h2 class="text-2xl brand-italic font-bold"><i class="fas fa-shopping-bag mr-2"></i>your cart</h2>
#       <button @click="showCart = false" class="w-9 h-9 rounded-full bg-white border border-[#dde3ed] text-[#1f2a3f]"><i class="fas fa-times"></i></button>
#     </div>
    
#     <div class="flex-1 overflow-y-auto p-5 space-y-4">
#       <template x-for="item in cart" :key="item.pid">
#         <!-- ADD THIS :class -->
#         <div
#           class="flex items-center gap-4 bg-white p-3 rounded-2xl shadow-sm border border-[#eef2f8]"
#           :class="!item.in_stock ? 'opacity-50' : ''"
#         >

#           <img :src="item.image" class="w-16 h-16 rounded-xl object-cover bg-[#f0f4fa]">

#           <div class="flex-1">

#             <!-- name -->
#             <h4 class="font-semibold" x-text="item.name"></h4>

#             <!-- ADD THIS WARNING TEXT -->
#             <p
#               x-show="!item.in_stock"
#               class="text-red-500 text-sm font-medium"
#             >
#               Out of stock
#             </p>

#             <div class="flex items-center justify-between mt-2">

#               <div class="flex items-center border border-[#dde3ed] rounded-full bg-white">

#                 <!-- MODIFY THIS BUTTON -->
#                 <button
#                   @click="removeOne(item.pid)"
#                   :disabled="!item.in_stock"
#                   class="px-3 py-1 text-[#1f2a3f] font-medium"
#                   :class="!item.in_stock ? 'opacity-40 cursor-not-allowed' : ''"
#                 >
#                   −
#                 </button>

#                 <span class="px-3 py-1 font-medium" x-text="item.quantity"></span>

#                 <!-- MODIFY THIS BUTTON -->
#                 <button
#                   @click="addToCart(item)"
#                   :disabled="!item.in_stock"
#                   class="px-3 py-1 text-[#1f2a3f] font-medium"
#                   :class="!item.in_stock ? 'opacity-40 cursor-not-allowed' : ''"
#                 >
#                   +
#                 </button>

#               </div>

#               <div class="flex items-center gap-3">

#                 <span
#                   class="font-bold text-[#1f2a3f]"
#                   x-text="'₦' + (item.price * item.quantity).toFixed(2)"
#                 ></span>

#                 <!-- REMOVE BUTTON -->
#                 <button
#                   @click="cart = cart.filter(i => i.pid !== item.pid); saveCart()"
#                   class="text-red-500 hover:text-red-700 font-bold text-lg"
#                   title="Remove item"
#                 >
#                   ✕
#                 </button>

#             </div>

#             </div>

#           </div>

#         </div>

#       </template>
#       <div x-show="cart.length === 0" class="text-center py-12 text-[#8e9aaf] flex flex-col items-center">
#         <i class="fas fa-box-open text-5xl mb-3 opacity-30"></i>
#         <p>your cart feels light</p>
#         <p class="text-sm">add some favorites</p>
#       </div>
#     </div>
    
#     <div class="border-t border-[#eef2f8] p-5 bg-white/80">
#       <div class="flex justify-between text-xl font-bold mb-4">
#         <span>Total</span>
#         <span class="text-[#1f2a3f]" x-text="'₦' + cartTotal"></span>
#       </div>
#       <button
#         @click="if(!hasOutOfStockItems) placeOrder()"
#         :disabled="hasOutOfStockItems"
#         :class="hasOutOfStockItems
#           ? 'bg-gray-400 cursor-not-allowed'
#           : 'bg-[#1f2a3f] hover:bg-[#2b384f] cursor-pointer'"
#         class="w-full text-white font-semibold py-4 rounded-2xl text-lg shadow-md flex items-center justify-center gap-3 transition-all"
#       >
#         <i class="fas fa-lock"></i>
#         <span x-text="hasOutOfStockItems ? 'Remove unavailable items' : 'CHECKOUT'"></span>
#       </button>

#     </div>
#   </div>
# </div>

# <!-- ===== CHECKOUT MODAL (order summary) ===== -->
# <div x-show="showCheckoutModal" class="fixed inset-0 z-50 flex items-center justify-center p-4" @keydown.escape.window="showCheckoutModal = false">
#   <div class="absolute inset-0 bg-black/10 backdrop-blur-sm" @click="showCheckoutModal = false"></div>
#   <div class="relative bg-white max-w-md w-full rounded-3xl p-6 shadow-2xl border border-[#eef2f8]"
#        x-show="showCheckoutModal" x-transition>
#     <h3 class="text-2xl brand-italic font-bold mb-1">order summary</h3>
#     <p class="text-sm text-[#6f7c91] font-mono">ref: <span x-text="orderId"></span></p>
    
#     <div class="my-5 max-h-60 overflow-y-auto space-y-3 pr-2">
#       <template x-for="item in cart" :key="item.pid">
#         <div class="flex justify-between items-center border-b border-[#edf2f9] pb-2">
#           <span><span class="font-bold" x-text="item.quantity"></span> × <span x-text="item.name"></span></span>
#           <span class="font-semibold" x-text="'₦' + (item.price * item.quantity).toFixed(2)"></span>
#         </div>
#       </template>
#     </div>
    
#     <div class="flex justify-between text-xl font-bold border-t border-[#dde3ed] pt-3">
#       <span>total</span>
#       <span x-text="'₦' + cartTotal"></span>
#     </div>
    
#     <div class="flex gap-3 mt-6">
#       <button @click="showCheckoutModal = false" class="flex-1 py-3 border border-[#cfdbe9] rounded-xl text-[#1f2a3f] font-medium">back</button>
#       <button @click="confirmOrder()" class="flex-1 bg-[#1f2a3f] text-white py-3 rounded-xl font-semibold shadow flex items-center justify-center gap-2">
#         <i class="fab fa-whatsapp"></i> confirm
#       </button>
#     </div>
#   </div>
# </div>

# <!-- ===== TOAST (bright and friendly) ===== -->
# <div x-show="toast.visible" x-cloak class="fixed bottom-8 left-1/2 -translate-x-1/2 z-[100] w-full max-w-md px-4">
#   <div class="toast-shop px-5 py-4 flex items-center gap-3 shadow-2xl"
#        x-transition:enter="transition ease-out duration-300" x-transition:enter-start="opacity-0 scale-90" x-transition:enter-end="opacity-100 scale-100"
#        x-transition:leave="transition ease-in duration-200" x-transition:leave-start="opacity-100 scale-100" x-transition:leave-end="opacity-0 scale-90">
#     <i class="fas fa-check-circle text-white text-xl"></i>
#     <span class="flex-1 text-sm" x-text="toast.message"></span>
#     <button @click="toast.visible = false" class="opacity-70 hover:opacity-100"><i class="fas fa-times"></i></button>
#   </div>
# </div>

# <!-- tiny style for line clamp -->
# <style>
#   .line-clamp-2 {
#     display: -webkit-box;
#     -webkit-line-clamp: 2;
#     -webkit-box-orient: vertical;
#     overflow: hidden;
#   }
#   [x-cloak] { display: none !important; }
# </style>

# </div>

# <!-- optional micro interaction (no gsap needed, but we keep pure css) -->
# </body>
# </html>

