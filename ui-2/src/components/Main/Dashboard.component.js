import React from "react";
import "./Dashboard.css";
import Navbars from "./NavbarMain";
import Sidebar from "./Sidebar";
function Main() {
  return (
    <>
      <div className="Main">
        <Navbars />
      </div>
      <div className="Sidebar">
        <Sidebar />
      </div>
    </>
  );
}

export default Main;
