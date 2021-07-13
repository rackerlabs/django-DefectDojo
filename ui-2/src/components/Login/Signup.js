import React from "react";
import Navbars from "./Navbar";
import "./Login.css";
function SignUp() {
  return (
    <div className="login">
      <Navbars />
      <div className="outer">
        <div className="inner">
          <form>
            <h3>Register</h3>

            <div className="form-group">
              <label for="firstname">First name</label>
              <input
                type="text"
                className="form-control"
                placeholder="First name"
                label="firstname"
                name="firstname"
              />
            </div>

            <div className="form-group">
              <label for="lastname">Last name</label>
              <input
                type="text"
                className="form-control"
                placeholder="Last name"
                name="lastname"
                label="lastname"
              />
            </div>

            <div className="form-group">
              <label for="email">Email</label>
              <input
                type="email"
                className="form-control"
                placeholder="Enter email"
                name="email"
                label="email"
              />
            </div>

            <div className="form-group">
              <label for="Password">Password</label>
              <input
                type="password"
                className="form-control"
                placeholder="Enter password"
                name="password"
                label="password"
              />
            </div>

            <button type="submit" className="btn btn-dark btn-lg btn-block">
              Register
            </button>
            <p className="forgot-password text-right">
              Already registered <a href="/sign-in">log in?</a>
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}
export default SignUp;
