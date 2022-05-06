import React, {Component} from 'react';
import {BrowserRouter as Router, Route, Switch, Redirect,withRouter} from "react-router-dom";
import "./assets/css/feather.css"
import "./assets/css/materialdesignicons.css"
import "./assets/css/dripiIcons.css"
import "./assets/css/fa.css"
import "./assets/css/fonts.css"
import './assets/css/semantic-ui-css/semantic.min.css'
import './App.css'
import 'react-toastify/dist/ReactToastify.css';
import Login from "./pages/auth/login"
import Main from "./pages/Main/Main";
import moment from "moment";
import { ToastContainer } from 'react-toastify';
import First_Create from "./pages/FirstWallet/First_Create";

export default class App extends Component {

    verifSession() {
        return !(localStorage.getItem("usrtoken") === null || localStorage.getItem("usrtoken") === undefined || parseInt(localStorage.getItem("exp")) < moment().unix());
    }



    render() {

        return (
            <>
                <Router>
                    <Switch>
                        <Redirect exact from={"/"} to={this.verifSession() === true ? "/main" : "/login"}/>
                        <Redirect exact from={"/"} to={"/main"}/>
                        <Route exact path="/login" component={Login}/>
                        <Route exact path="/create_wallet" component={First_Create}/>
                        <Route path="/main" component={withRouter(Main)}/>
                    </Switch>
                </Router>

                <ToastContainer
                    containerId="id"
                    draggable={false}
                    autoClose={3000}
                />

            </>
        )
    }

}




