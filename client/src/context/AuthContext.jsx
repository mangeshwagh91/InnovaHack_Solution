import { createContext, useContext, useState, useEffect } from "react";
import api from "../api/client";

const AuthContext = createContext();

const AUTH_KEY = "dcpi_demo_auth";
const USER_KEY = "dcpi_demo_user";

export function AuthProvider({ children }) {
  const [isAuthenticated, setIsAuthenticated] = useState(() => {
    return sessionStorage.getItem(AUTH_KEY) === "true";
  });
  
  const [user, setUser] = useState(() => {
    try {
      const stored = sessionStorage.getItem(USER_KEY);
      return stored ? JSON.parse(stored) : null;
    } catch (_) {
      return null;
    }
  });
  
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  useEffect(() => {
    sessionStorage.setItem(AUTH_KEY, isAuthenticated);
    if (user) {
      sessionStorage.setItem(USER_KEY, JSON.stringify(user));
    } else {
      sessionStorage.removeItem(USER_KEY);
    }
  }, [isAuthenticated, user]);

  const loginAsTeam = () => {
    setUser({
      type: "team",
      name: "EPC Project Manager",
      email: "pm@dcpi.ai",
    });
    setIsAuthenticated(true);
  };

  const loginAsVendorDemo = () => {
    setUser({
      type: "vendor",
      id: "demo-vendor",
      name: "Delta Systems",
      email: "vendor@delta.com",
    });
    setIsAuthenticated(true);
  };
  
  const loginAsVendor = async (email, password) => {
    try {
      const data = await api.loginVendor(email, password);
      setUser({
        type: "vendor",
        id: data.vendor_id,
        name: email.split("@")[0].toUpperCase() + " Corp",
        email: email,
        token: data.access_token,
      });
      setIsAuthenticated(true);
      return { success: true };
    } catch (err) {
      console.error("Vendor login failed:", err);
      throw err;
    }
  };

  const registerVendor = async (companyName, email, password) => {
    try {
      const data = await api.registerVendor({
        company_name: companyName,
        email: email,
        password: password,
      });
      return data;
    } catch (err) {
      console.error("Vendor registration failed:", err);
      throw err;
    }
  };
  
  const logout = () => {
    setIsAuthenticated(false);
    setUser(null);
    setIsLoggingOut(false);
  };

  return (
    <AuthContext.Provider value={{ 
      isAuthenticated, 
      isLoggingOut, 
      user,
      loginAsTeam,
      loginAsVendor,
      loginAsVendorDemo,
      registerVendor,
      logout 
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
