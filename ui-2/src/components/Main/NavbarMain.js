import React, { Component } from "react";
import "./NavbarMain.css";

import {
  Navbar,
  NavDropdown,
  Button,
  Form,
  FormControl,
} from "react-bootstrap";

import "bootstrap/dist/css/bootstrap.min.css";
/////////////////// Material UI//////////////////////////////////////
import SearchIcon from "@material-ui/icons/Search";
import NotificationsIcon from "@material-ui/icons/Notifications";
import PersonIcon from "@material-ui/icons/Person";
import InfoIcon from "@material-ui/icons/Info";
import VpnKeyIcon from "@material-ui/icons/VpnKey";
import DescriptionIcon from "@material-ui/icons/Description";
import AssignmentIcon from "@material-ui/icons/Assignment";
import ExitToAppIcon from "@material-ui/icons/ExitToApp";
import ArrowForwardIosIcon from "@material-ui/icons/ArrowForwardIos";
////////////////////////////React Icon//////////////////////////

export default class Navbars extends Component {
  render() {
    return (
      <div className="navbar__main">
        <Navbar bg="light" variant="light" fixed="top">
          <div className="navbar__left">
            <Navbar.Brand href="#home">
              <img
                src="https://demo.defectdojo.org/static/dojo/img/logo.png"
                alt="DefectDojo-logo"
                width="240px"
              />
            </Navbar.Brand>
          </div>

          {/* Search Input */}
          <div className="navbar__right ml-auto">
            <Form inline>
              <FormControl
                type="text"
                placeholder="Search"
                className="mr-sm-2"
                label="Search"
                aria-label="Search"
                name="query"
              />
              <Button
                variant="dark"
                id="submit_Search"
                aria-label="Serach"
                size="sm"
              >
                <SearchIcon />
              </Button>
            </Form>
            {/* Notification downbar */}
            <NavDropdown
              alignRight
              title={<NotificationsIcon />}
              id="basic-nav-dropdown"
              dropdown-menu-left
            >
              <NavDropdown.Item href="/engagement/24">
                <div className="navbardown__item">
                  <InfoIcon />
                  <h6>2021-02-09 for Prueba PPS</h6>
                </div>
              </NavDropdown.Item>
              <NavDropdown.Divider />
              <NavDropdown.Item href="#action/3.2">
                <div className="navbardown__item">
                  <InfoIcon />
                  <h6> Engagement created for Prueba PPS:2021-02-09</h6>
                </div>
              </NavDropdown.Item>
              <NavDropdown.Divider />
              <NavDropdown.Item href="#action/3.3">
                <div className="navbardown__item">
                  <InfoIcon />
                  <h6> 2021-02-09 for Prueba PPS </h6>
                </div>
              </NavDropdown.Item>
              <NavDropdown.Divider />
              <NavDropdown.Item href="#action/3.4">
                <div className="navbardown__item">
                  <InfoIcon />{" "}
                  <h6> Engagement created for Prueba PPS:2021-02-09</h6>
                </div>
              </NavDropdown.Item>
              <NavDropdown.Divider />
              <NavDropdown.Item href="#action/3.4">
                <div className="navbardown__item">
                  <InfoIcon />
                  <h6> Engagement created for Prueba PPS:Ad Hoc Engage....</h6>
                </div>
              </NavDropdown.Item>
              <NavDropdown.Divider />
              <NavDropdown.Item href="#action/3.4">
                <div className="navbardown__item">
                  <InfoIcon />
                  <h6>Test</h6>
                </div>
              </NavDropdown.Item>
              <NavDropdown.Divider />
              <NavDropdown.Item href="#action/3.4">
                <div className="navbardown__item">
                  <InfoIcon />
                  <h6> Test Product for Test Company</h6>
                </div>
              </NavDropdown.Item>
              <NavDropdown.Divider />
              <NavDropdown.Item href="#action/3.4">
                <div className="navbardown__item">
                  <InfoIcon /> <h6>Deletion of Internal CRM App</h6>
                </div>
              </NavDropdown.Item>
              <NavDropdown.Divider />
              <NavDropdown.Item href="#action/3.4">
                <div className="navbardown__item">
                  <InfoIcon /> <h6> 2021-02-08 for Bodgelt</h6>
                </div>
              </NavDropdown.Item>
              <NavDropdown.Divider />
              <NavDropdown.Item href="#action/3.4">
                <div className="navbardown__item">
                  <InfoIcon />
                  <h6> Engagement created for Bodgelt:2021-02-08</h6>
                </div>
              </NavDropdown.Item>
              <NavDropdown.Divider />
              <NavDropdown.Item href="#action/3.4">
                <div className="navbardown__item">
                  <InfoIcon /> <h6> 2021-02-08 for Bodgelt</h6>
                </div>
              </NavDropdown.Item>
              <NavDropdown.Divider />
              <NavDropdown.Item href="#action/3.4">
                <div className="navbardown__item">
                  <InfoIcon />
                  <h6> Engagement created for Bodgelt:2021-02-08</h6>
                </div>
              </NavDropdown.Item>
              <NavDropdown.Divider />
              <NavDropdown.Item>
                <h5>
                  See All Alerts
                  {<ArrowForwardIosIcon />}
                </h5>
              </NavDropdown.Item>
              <NavDropdown.Divider />
              <NavDropdown.Item>
                <h5>
                  Clear All Alert
                  {<ArrowForwardIosIcon />}
                </h5>
              </NavDropdown.Item>
            </NavDropdown>
            {/* Profile Downbar */}
            <NavDropdown
              alignRight
              title={<PersonIcon />}
              id="basic-nav-dropdown"
              dropdown-menu-left
            >
              <NavDropdown.Item href="#action/3.4">
                <div className="navbardown__item">
                  <PersonIcon />
                  <h6> admin</h6>
                </div>
              </NavDropdown.Item>
              <NavDropdown.Item href="#action/3.4">
                <div className="navbardown__item">
                  <VpnKeyIcon />
                  <h6> API v1 Key</h6>
                </div>
              </NavDropdown.Item>
              <NavDropdown.Item href="#action/3.4">
                <div className="navbardown__item">
                  <VpnKeyIcon />
                  <h6> API v2 Key</h6>
                </div>
              </NavDropdown.Item>
              <NavDropdown.Item href="#action/3.4">
                <div className="navbardown__item">
                  <DescriptionIcon />
                  <h6> API v1 Docs</h6>
                </div>
              </NavDropdown.Item>
              <NavDropdown.Item href="#action/3.4">
                <div className="navbardown__item">
                  <DescriptionIcon />
                  <h6> API v2 Docs</h6>
                </div>
              </NavDropdown.Item>
              <NavDropdown.Item href="#action/3.4">
                <div className="navbardown__item">
                  <AssignmentIcon />
                  <h6> Questionnaires</h6>
                </div>
              </NavDropdown.Item>
              <NavDropdown.Item href="#action">
                <div className="navbardown__item">
                  <ExitToAppIcon />
                  <h6>Log Out</h6>
                </div>
              </NavDropdown.Item>
            </NavDropdown>
          </div>
        </Navbar>
      </div>
    );
  }
}
