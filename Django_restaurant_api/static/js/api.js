import axios from "https://cdn.jsdelivr.net/npm/axios@1.6.8/dist/axios.min.js";

export const api = axios.create({
    baseURL: "http://127.0.0.1:8000/",
    timeout: 10000,
    headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
    },
});

// Global error handling
api.interceptors.response.use(
    response => response,
    error => {
        console.error("API Error:", error.response?.data || error.message);
        return Promise.reject(error);
    }
);
