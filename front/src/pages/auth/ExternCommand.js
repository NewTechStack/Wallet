import React from "react";
import {verifSession} from "../../tools/functions";
import LinearProgress from "@material-ui/core/LinearProgress";
import {Progress} from "semantic-ui-react";
import login_gif from "../../assets/gifs/login2.gif";
import Button from "@material-ui/core/Button";
import MuiBackdrop from "../../components/Loading/MuiBackdrop";
import empty_icon from "../../assets/icons/empty_icon2.png"
import CircularProgress from "@material-ui/core/CircularProgress";
import {toast} from 'react-toastify';
import WalletService from "../../provider/walletService";


export default class ExternCommand extends React.Component{

    state={
        firstLoading:true,
        loading:false,
        error:true,
        textError:null
    }

    componentDidMount() {



        if(verifSession() === false){
            if(this.props.match.params && this.props.match.params.cmd && this.props.match.params.cmd !== "" ){
                localStorage.setItem("cmd",this.props.match.params.cmd)
                this.props.history.push("/login")
            }else{
                this.props.history.push("/login")
            }

        }else{
            let cmd = this.props.match.params.cmd
            try {
                let formated_data = JSON.parse(atob(cmd))
                console.log(formated_data)
                this.setState({firstLoading:false,error:false,data:formated_data})


                if(formated_data.chain && formated_data.cmd_list && formated_data.kwargs){

                    WalletService.deployCmd(formated_data.chain.name,formated_data.chain.type,formated_data.chain.contract_type,formated_data,localStorage.getItem("usrtoken"))
                        .then( res => {

                        if(res.status === 200 && res.succes === true){
                            localStorage.removeItem("cmd")
                            toast.success("Opération effectuée avec succès !", {
                                position: toast.POSITION.TOP_CENTER
                            });
                            setTimeout(() => {
                                window.location.replace(formated_data.redirect + "/" + res.data.contract.id + "/" + res.data.contract.address)
                            },5000)
                        }else{
                            this.setState({textError:"Une erreur est survenue, veuillez recharger la page et réessayer"})
                            localStorage.removeItem("cmd")
                            toast.error(res.error, {
                                position: toast.POSITION.TOP_CENTER
                            });
                        }

                    }).catch( err => {
                        this.setState({textError:"Une erreur est survenue, veuillez recharger la page et réessayer"})
                        localStorage.removeItem("cmd")
                        toast.error("Une erreur est survenue, veuillez recharger la page", {
                            position: toast.POSITION.TOP_CENTER
                        });
                        console.log(err)
                    })
                }else{
                    this.setState({textError:"Une erreur est survenue, veuillez recharger la page et réessayer"})
                    localStorage.removeItem("cmd")
                    toast.error("Une erreur est survenue, veuillez recharger la page", {
                        position: toast.POSITION.TOP_CENTER
                    });
                }

            }catch (err){
                console.log(err)
                localStorage.removeItem("cmd")
                this.setState({error:true,firstLoading:false,loading:true})
                toast.error("Une erreur est survenue, veuillez recharger la page", {
                    position: toast.POSITION.TOP_CENTER
                });
            }

        }
    }



    render() {
        return(
            <div>
                <MuiBackdrop open={this.state.firstLoading || this.state.loading} />
                <div className="container container-lg" style={{marginTop:120}}>

                    <div className="login_form">
                        {
                            (this.state.firstLoading === true ) ?
                                <LinearProgress /> :
                                this.state.error === false && <Progress active={false} percent={100} size="medium" className="custom-progress-height" color='blue' />
                        }

                        {
                            this.state.error === false &&
                            <div>
                                <div className="padding-form" >

                                    <div align="center">
                                        <div style={{display:"flex",justifyContent:"center",marginTop:15}}>
                                            <div style={{alignSelf:"center"}}>
                                                <img alt="login"
                                                     src={(this.state.data.metadata && this.state.data.metadata.img) ? ("data:image/png;base64," + this.state.data.metadata.img) : empty_icon  }
                                                     style={{width:60,height:60,objectFit:"cover",borderRadius:"50%"}}/>
                                            </div>
                                            <div style={{alignSelf:"center",marginLeft:5}}>
                                                <h4>{this.state.data.kwargs.name}</h4>
                                                <h5 style={{marginTop:-12}}>{this.state.data.kwargs.symbol}</h5>
                                            </div>
                                        </div>
                                        <div style={{marginTop:30}}>
                                            <h5>{"Création de " + this.state.data.kwargs.initialSupply +  " tokens en cours..." }</h5>
                                            <h5 style={{marginTop:-10}}>Distribution...</h5>
                                        </div>
                                        <div style={{marginTop:30}}>
                                            {
                                                this.state.textError && this.state.textError !== "" ?
                                                    <div style={{color:"red"}}>
                                                        <h6>{this.state.textError}</h6>
                                                        <div align="center" className="mt-3">
                                                            <Button variant="contained" style={{textTransform:"none",marginLeft:15,fontWeight:"bold"}} color="primary"
                                                                    onClick={() => {
                                                                        window.location.reload()
                                                                    }}
                                                            >Recharger</Button>
                                                        </div>
                                                    </div> :
                                                    <CircularProgress color="primary" size={30} />
                                            }

                                        </div>
                                    </div>

                                </div>
                            </div>
                        }


                    </div>


                </div>

            </div>
        )
    }


}
