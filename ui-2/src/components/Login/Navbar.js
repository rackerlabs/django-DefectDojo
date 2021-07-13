import React from "react";
import { Navbar, NavbarBrand, Nav } from "react-bootstrap/";
import "bootstrap/dist/css/bootstrap.min.css";
import { Link } from "react-router-dom";

export default function Navbars() {
  return (
    <div>
      <Navbar collapseOnSelect expand="lg" bg="light">
        <Nav className="mr-auto">
          <NavbarBrand>
            <Link to={"/sign-in"}>
              <img src="/Images/logo.png" alt="Defectdojo-logo" width="240px" />
            </Link>
          </NavbarBrand>
        </Nav>
        <Navbar.Toggle aria-controls="responsive-navbar-nav" />
        <Navbar.Collapse id="responsive-navbar-nav">
          <ul className="navbar-nav ml-auto">
            <li className="nav-item">
              <Link className="nav-link" to={"/sign-in"}>
                Sign in
              </Link>
            </li>
            <li className="nav-item">
              <Link className="nav-link" to={"/sign-up"}>
                Sign up
              </Link>
            </li>
          </ul>
        </Navbar.Collapse>
      </Navbar>
    </div>
  );
}
