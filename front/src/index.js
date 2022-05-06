import React from 'react';
import ReactDOM from 'react-dom';
import App from './App';
import * as serviceWorker from './serviceWorker';
import {ThemeProvider} from '@material-ui/styles';
import {createMuiTheme} from '@material-ui/core/styles';
import "./index.css"
import '@fontsource/roboto';
import {primaryColor} from "./constants/defaultValues";

const theme = createMuiTheme({
    palette: {
        primary: {
            main: primaryColor,
        },
        secondary: {
            main: 'rgb(20, 88, 148)',
        },
        custom: {
            main: primaryColor
        }

    },
});

ReactDOM.render(
    <ThemeProvider theme={theme}>
        <div id="layout-wrapper">
            <App/>,
        </div>
    </ThemeProvider>
    ,
    document.getElementById('root'));

// If you want your app to work offline and load faster, you can change
// unregister() to register() below. Note this comes with some pitfalls.
// Learn more about service workers: https://bit.ly/CRA-PWA
serviceWorker.unregister();
