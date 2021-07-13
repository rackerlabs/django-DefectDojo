import React from "react";
import classNames from "classnames";
import PropTypes from "prop-types";
//@material-ui/core components
import { makeStyles } from "@material-ui/core/styles";
import { AppBar, Toolbar, IconButton, Hidden } from "@material-ui/core";
// @material-ui/icons
import Menu from "@material-ui/icons/Menu";

import AdminNavbarLinks from "./AdminNavbarLinks";
import Button from "../CustomButton/Button";

import styles from "../../Styles/jss/components/headerStyle";

const useStyles = makeStyles(styles);

function Header(props) {
  const classes = useStyles();
  function makeBrand() {
    var name;
    props.routes.map((prop) => {
      if (window.location.href.indexOf(prop.path) !== -1) {
        name = prop.name;
      }
      return null;
    });
    return name;
  }
  const { color } = props;
  const appBarClasses = classNames({
    [" " + classes[color]]: color,
  });
  return (
    <AppBar className={classes.appBar + appBarClasses}>
      <Toolbar className={classes.container}>
        <div className={classes.flex}>
          {/* Here we create navbar brand, based on route name */}
          <Button color="transparent" href="#" className={classes.title}>
            {makeBrand()}
          </Button>
        </div>
        <Hidden smDown implementation="css">
          <AdminNavbarLinks />
        </Hidden>
        <Hidden mdUp implementation="css">
          <IconButton
            color="inherit"
            aria-label="open drawer"
            onClick={props.handleDrawerToggle}
          >
            <Menu />
          </IconButton>
        </Hidden>
      </Toolbar>
    </AppBar>
  );
}
export default Header;
Header.propTypes = {
  color: PropTypes.oneOf(["primary", "info", "success", "warning", "danger"]),

  handleDrawerToggle: PropTypes.func,
  routes: PropTypes.arrayOf(PropTypes.object),
};
