import React from "react";
import styles from "./Login.module.css";
import Navbars from "./Navbar";

function Login() {
  return (
    <div className={styles.login}>
      <section>
        <Navbars />
      </section>
      <div className={styles.outer}>
        <div className={styles.inner}>
          <form>
            <h3>Log in</h3>

            <div className="form-group">
              <label for="email">Email</label>
              <input
                id="email"
                label="email"
                type="email"
                className="form-control"
                placeholder="Enter email"
              />
            </div>

            <div className="form-group">
              <label for="password">Password</label>
              <input
                id="password"
                label="password"
                type="password"
                className="form-control"
                placeholder="Enter password"
              />
            </div>

            <div className="form-group">
              <div className="custom-control custom-checkbox">
                <input
                  id="customCheck1"
                  label="checkbox"
                  type="checkbox"
                  className="custom-control-input"
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
              Forgot{" "}
              <a className={styles.ancor} href="www.google.com">
                password?
              </a>
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}
export default Login;
