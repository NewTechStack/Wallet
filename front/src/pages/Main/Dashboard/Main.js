import {Redirect, Route, Switch,withRouter} from "react-router-dom";
import React from "react";
import All from "./All";



export default class Main extends React.Component{


    componentDidMount() {
        this.props.setCurrentPage()

    }


    render() {
        return(

            <Switch>
                <Redirect exact from={"/main/dashboard"} to="/main/dashboard/all"/>
                <Route path={'/main/dashboard/all'}
                       render={routeProps => <All {...routeProps}/>}
                />
            </Switch>
        )
    }


}
