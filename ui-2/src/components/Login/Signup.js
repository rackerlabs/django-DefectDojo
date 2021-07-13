import React from "react";
import Navbars from "./Navbar";
import styles from "./Login.module.css";
function SignUp() {
  return (
    <div className={styles.login}>
      <Navbars />
      <div className={styles.outer}>
        <div className={styles.inner}>
          <form>
            <h3>Register</h3>

            <div className="form-group">
              <label for="firstname">First name</label>
              <input
                id="firstname"
                type="text"
                className="form-control"
                placeholder="First name"
                label="firstname"
              />
            </div>

            <div className="form-group">
              <label for="lastname">Last name</label>
              <input
                id="lastname"
                type="text"
                className="form-control"
                placeholder="Last name"
                label="lastname"
              />
            </div>

            <div className="form-group">
              <label for="email">Email</label>
              <input
                id="email"
                type="email"
                className="form-control"
                placeholder="Enter email"
                label="email"
              />
            </div>

            <div className="form-group">
              <label for="Password">Password</label>
              <input
                id="password"
                type="password"
                className="form-control"
                placeholder="Enter password"
                label="password"
              />
            </div>

            <button type="submit" className="btn btn-dark btn-lg btn-block">
              Register
            </button>
            <p className="forgot-password text-right">
              Already registered{" "}
              <a className={styles.ancor} href="/sign-in">
                log in?
              </a>
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}
export default SignUp;
