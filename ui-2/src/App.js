import React from "react";

import "./App.css";
import { BrowserRouter as Router, Switch, Route } from "react-router-dom";

import Login from "./components/Login/Login";
import SignUp from "./components/Login/Signup";
import Main from "./components/Main/main";

function App() {
  return (
    <Router>
      <div className="App">
        <Switch>
          <Route exact path="/" component={Login} />
          <Route exact path="/sign-in" component={Login} />
          <Route exact path="/sign-up" component={SignUp} />
          <Route path="/dashboard" component={Main} />
          <Route path="/product" component={Main} />
          <Route path="/engagements" component={Main} />
        </Switch>
      </div>
    </Router>
  );
}

export default App;
