console.log("dashboard.js loaded");

const api = axios.create({
    baseURL: "http://127.0.0.1:8000/",
    timeout: 10000,
    headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
    },
});

// Global error handler
api.interceptors.response.use(
    response => response,
    error => {
        console.error("API Error:", error.response?.data || error.message);
        return Promise.reject(error);
    }
);

async function loadRevenue() {
    try {
        console.log("Calling dashboard API...");

        const { data } = await api.get("useradmin/api/dashboard/");
        console.log("API response:", data);

        // safely extract values with defaults
        const revenue = Number(data?.revenue) || 0;
        const monthlyRevenue = Number(data?.monthly_revenue) || 0;
        const totalOrders = data?.total_orders_count || 0;
        const products = data?.all_products || [];
        const newCustomers = data?.new_customers || [];
        // const latestOrders = data?.latest_orders || [];

        // update UI
        document.getElementById('revenue-amount').textContent = `₦${revenue.toLocaleString()}`;
        document.getElementById('monthly-revenue').textContent = `₦${monthlyRevenue.toLocaleString()}`;
        document.getElementById('total-orders').textContent = totalOrders;
        document.getElementById('total-products').textContent = products.length;
        
        console.log("Dashboard loaded successfully");


        // after you extract latestOrders from API
        const latestOrders = data?.latest_orders || [];

        // select the table body
        const tbody = document.querySelector("table tbody");
        tbody.innerHTML = ""; // clear old rows

        // loop through the orders and create table rows
        latestOrders.forEach(order => {
            const row = document.createElement("tr");

            row.innerHTML = `
                <td class="text-center">
                    <div class="form-check">
                        <input class="form-check-input" type="checkbox" />
                        <label class="form-check-label"></label>
                    </div>
                </td>
                <td><a href="#" class="fw-bold">${order.bid || "-"}</a></td>
                <td>${order.customer_name || "Unknown"}</td>
                <td>${order.date_created ? new Date(order.date_created).toLocaleDateString() : "-"}</td>
                <td>₦${Number(order.total_price || 0).toLocaleString()}</td>
                <td>
                    <span class="badge badge-pill ${order.payment_status === "paid" ? "badge-soft-success" : "badge-soft-danger"}">
                        ${order.payment_status ? order.payment_status.charAt(0).toUpperCase() + order.payment_status.slice(1) : "Unknown"}
                    </span>
                </td>
                <td><a href="#" class="btn btn-xs">View details</a></td>
            `;
            tbody.appendChild(row); // add the row to the table
        });


    } catch (err) {
        console.error("Error loading dashboard:", err);
        document.getElementById("revenue-amount").textContent = "unavailable";
        document.getElementById("monthly-revenue").textContent = "unavailable";
        document.getElementById("total-orders").textContent = "-";
        document.getElementById("total-products").textContent = "-";
    }
}

loadRevenue();
setInterval(loadRevenue, 10000);





// import { api } from './api.js' // “Bring in the api object from the file api.js.”

// async function loadRevenue() {
//     try {

//         console.log("Calling dashboard API...");

//         // 👉 Sends a GET request to: http://127.0.0.1:8000/useradmin/api/dashboard
//         const { data } = await api.get("useradmin/api/dashboard");
//         console.log("API response:", data);
//         const revenue = data.revenue || 0;

//         document.getElementById('revenue-amount').textContent = 
//         `₦${Number(revenue).toLocaleString()}`; // toLocaleString() is use to humanize the amount
//     }
//     catch (err) {
//         document.getElementById("revenue-amount").textContent = "unavailable";
//     }
// }

// // “When the page finishes loading HTML, call loadRevenue().”
// document.addEventListener("DOMContentLoaded", loadRevenue);

// // “Every 10,000 milliseconds (10 seconds), call loadRevenue() again.”
// setInterval(loadRevenue, 10000);
