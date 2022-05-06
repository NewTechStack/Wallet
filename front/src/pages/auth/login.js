import React, {Component} from "react";
import MuiBackdrop from "../../components/Loading/MuiBackdrop";
import extern_sso_service from "../../provider/extern_sso_service";
import { Progress } from 'semantic-ui-react'
import Button from '@material-ui/core/Button';
import LinearProgress from '@material-ui/core/LinearProgress';
import "./login_signup.css"
import login_gif from "../../assets/gifs/login2.gif"
import jwt_decode from "jwt-decode";
import moment from "moment";
import WalletService from "../../provider/walletService";


const popup_w = 900;
const popup_h = 700;

var dualScreenLeft = window.screenLeft !== undefined ? window.screenLeft : window.screen.left;
var dualScreenTop = window.screenTop !== undefined ? window.screenTop : window.screen.top;

var width = window.innerWidth ? window.innerWidth : document.documentElement.clientWidth ? document.documentElement.clientWidth : window.screen.width;
var height = window.innerHeight ? window.innerHeight : document.documentElement.clientHeight ? document.documentElement.clientHeight : window.screen.height;

var left = ((width / 2) - (popup_w / 2)) + dualScreenLeft;
var top = ((height / 2) - (popup_h / 2)) + dualScreenTop;




class login extends Component {



    state = {
        loading:false,
    };


    componentDidMount() {
        /*this.props.history.push("/main")*/
        if(this.verifSession() === true){
            this.props.history.push("/main")
        }
    }


    verifSession(){
        return !(localStorage.getItem("usrtoken") === null || localStorage.getItem("usrtoken") === undefined || parseInt(localStorage.getItem("exp")) < moment().unix());
    }

    conn(){
        this.setState({loading:true})
        setTimeout(() => {

            extern_sso_service.sso().then( res => {
                if(res.status === 200 && res.succes === true){

                    var newWindow = window.open(res.data.url, "Login", 'scrollbars=yes, width=' + popup_w + ', height=' + popup_h + ', top=' + top + ', left=' + left);
                    if (window && window.focus) {
                        newWindow.focus();
                    }

                    extern_sso_service.conn(res.data.id).then( connRes => {

                        console.log(connRes)
                        if(connRes && connRes.data){

                            var decoded = jwt_decode(connRes.data.usrtoken);
                            console.log(decoded)
                            localStorage.setItem("usrtoken",connRes.data.usrtoken)
                            localStorage.setItem("exp",decoded.exp)
                            localStorage.setItem("email",decoded.payload.email)
                            localStorage.setItem("username",decoded.payload.username)
                            localStorage.setItem("id",decoded.payload.id)
                            localStorage.setItem("roles",JSON.stringify(decoded.payload.roles))
                            this.setState({loading:false})
                            newWindow.close()

                            WalletService.get_wallets(connRes.data.usrtoken).then( res => {

                                console.log(res)
                                if(res.status === 200 && res.succes === true){
                                    if(res.data && res.data.wallets){

                                        if(res.data.wallets.length === 0){
                                            this.props.history.push("/create_wallet");
                                        }else{
                                            this.props.history.push("/main");
                                        }

                                    }else{
                                        console.log("Une erreur est survenue")
                                    }

                                }else{
                                    console.log(res.error)
                                }

                            }).catch( err => {
                                console.log(err)
                            })

                            //this.props.history.push("/main");

                        }else{

                        }


                    }).catch(err => {console.log(err)})


                }else{
                    console.log(res.error)
                }

            }).catch( err => {
                console.log(err)
            })

        },500)
    }

    render() {

        return (
            <>
                <MuiBackdrop open={this.state.loading}  />

                <div className="container container-lg" style={{marginTop:120}}>

                    <div className="login_form">
                        {
                            this.state.loading === true ?
                                <LinearProgress /> :
                                <Progress active={false} percent={100} size="medium" className="custom-progress-height" color='blue' />
                        }

                        <div>
                            <div className="padding-form" >

                                <div align="center">
                                    <img alt="login" src={login_gif} style={{width:250,objectFit:"cover"}}/>
                                </div>


                                <h4 style={{fontSize:"1.4rem",marginBottom:5,marginTop:-15}}>Veuillez vous connecter !</h4>
                                <h6 style={{fontSize:"0.9rem",marginBottom:5,color:"grey"}}>Vous pouvez vous connecter ou vous s'inscrire sur le lien suivant</h6>

                                <form id="login-form" style={{maxWidth:500,alignSelf:"center"}}
                                      onSubmit={(e) => {
                                          e.preventDefault(); e.stopPropagation();
                                          this.conn()
                                      }}
                                >
                                    <div align="center" className="mt-5">
                                        <Button type="submit" variant="contained" style={{textTransform:"none",marginLeft:15,fontWeight:"bold"}} color="primary">Se connecter</Button>
                                    </div>
                                </form>
                            </div>
                        </div>

                    </div>


                </div>
            </>
        )

    }

}


export default login
