import React from "react";
import "./Login.css";
import Navbars from "./Navbar";
function Login() {
  return (
    <div className="login">
      <section>
        <Navbars />
      </section>
      <div className="outer">
        <div className="inner">
          <form>
            <h3>Log in</h3>

            <div className="form-group">
              <label for="email">Email</label>
              <input
                label="email"
                type="email"
                className="form-control"
                placeholder="Enter email"
                name="email"
              />
            </div>

            <div className="form-group">
              <label for="password">Password</label>
              <input
                label="password"
                type="password"
                className="form-control"
                placeholder="Enter password"
                name="password"
              />
            </div>

            <div className="form-group">
              <div className="custom-control custom-checkbox">
                <input
                  label="checkbox"
                  type="checkbox"
                  className="custom-control-input"
                  id="customCheck1"
                />
                <label
                  className="custom-control-label"
                  htmlFor="customCheck1"
                  for="customCheck1"
                >
                  Remember me
                </label>
              </div>
            </div>

            <button type="submit" className="btn btn-dark btn-lg btn-block">
              Sign in
            </button>
            <p className="forgot-password text-right">
              {" "}
              Forgot <a href="www.google.com">password?</a>
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}
export default Login;
