import React, {Component} from "react";
import MuiBackdrop from "../../components/Loading/MuiBackdrop";
import LinearProgress from "@material-ui/core/LinearProgress";
import {Progress} from "semantic-ui-react";
import wallet_gif from "../../assets/gifs/wallet_2.gif";
import wallet_gif_2 from "../../assets/gifs/wallet_1.gif";
import secure_wallet from "../../assets/icons/secure_wallet.jpg";
import Button from "@material-ui/core/Button";
import TextArea from '@atlaskit/textarea'
import recovery_img from "../../assets/images/recovery_secret.png"
import WalletService from "../../provider/walletService";
import {toast} from 'react-toastify';
import Textfield from '@atlaskit/textfield';

export default class First_Create extends Component{


    state = {
        loading:false,
        active_form:"first",
        recovery_secret:true,
        recovery_phrase:"",
        wallet_name:""
    };



    componentDidMount() {

        this.setState({loading:true})
        WalletService.get_wallets(localStorage.getItem("usrtoken")).then( res => {

            if(res.status === 200 && res.succes === true){
                if(res.data && res.data.wallets){
                    if(res.data.wallets.length > 0){
                        this.setState({loading:false})
                        this.props.history.push("/main");
                    }
                }else{
                    this.props.history.push("/login");
                }

            }else{
                console.log(res.error)
                this.props.history.push("/login");
            }

        }).catch( err => {
            console.log(err)
            this.props.history.push("/login");
        })

    }

    create_wallet(){
        this.setState({loading:true})
        setTimeout(() => {
            WalletService.add_wallet(localStorage.getItem("usrtoken"),{name:this.state.wallet_name || ""}).then( res => {
                if(res.status === 200 && res.succes === true){
                    toast.success("Votre portefeuille est crée avec succès !", {
                        position: toast.POSITION.TOP_RIGHT
                    });
                    this.setState({recovery_phrase:res.data.mnemonic,loading:false,active_form:"third"})
                }else{
                    toast.error(res.error, {
                        position: toast.POSITION.TOP_RIGHT
                    });
                }
            }).catch(err => {
                console.log(err)
            })
        },3000)

    }



    render() {
        return(
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
                            {
                                this.state.active_form === "first" &&
                                <div className="padding-form" >

                                    <div align="center">
                                        <img alt="login" src={wallet_gif} style={{width:250,objectFit:"cover"}}/>
                                    </div>


                                    <h4 style={{fontSize:"1.4rem",marginBottom:5,marginTop:20,textAlign:"center"}}>Bienvenue dans la Beta de Rocket Wallet !</h4>
                                    <h5 style={{fontSize:"0.9rem",marginBottom:5,marginTop:20,color:"grey",textAlign:"center"}}>
                                        Rocket Wallet est un coffre sécurisé pour votre identité sur la Blockchain</h5>

                                    <div align="center" className="mt-5">
                                        <Button variant="contained" style={{textTransform:"none",marginLeft:15,fontWeight:"bold"}} color="primary"
                                                onClick={() => {
                                                    this.setState({active_form:"second"})
                                                }}
                                        >
                                            Démarrer</Button>
                                    </div>
                                </div>
                            }

                            {
                                this.state.active_form === "second" &&
                                <div className="padding-form" >

                                    <div align="center">
                                        <img alt="login" src={wallet_gif_2} style={{width:250,objectFit:"cover"}}/>
                                    </div>


                                    <h4 style={{fontSize:"1.4rem",marginBottom:5,marginTop:20,textAlign:"center"}}>Passons à la configuration !</h4>
                                    <h5 style={{fontSize:"0.9rem",marginBottom:5,marginTop:20,color:"grey",textAlign:"center"}}>
                                        Cela créera un nouveau portefeuille et une nouvelle phrase mnémotechnique</h5>
                                    <div style={{marginTop:15}}>
                                        <Textfield
                                            name="basic1"
                                            value={this.state.wallet_name}
                                            onChange={(e => {
                                                this.setState({wallet_name:e.target.value})
                                            })}
                                            placeholder="Choisissez un nom pour votre portefeuille"
                                        />
                                    </div>

                                    <div align="center" className="mt-5">
                                        <Button variant="contained" style={{textTransform:"none",marginLeft:15,fontWeight:"bold"}} color="primary"
                                                onClick={() => {
                                                    this.create_wallet()
                                                }}
                                        >Créer un portefeuille</Button>
                                    </div>
                                </div>
                            }

                            {
                                this.state.active_form === "third" &&
                                <div className="padding-form" >

                                    <div align="center">
                                        <img alt="login" src={secure_wallet} style={{width:250,objectFit:"cover"}}/>
                                    </div>


                                    <h4 style={{fontSize:"1.4rem",marginBottom:5,marginTop:20,textAlign:"center"}}>Sécuriser votre portefeuille </h4>
                                    <div style={{marginTop:20}}>
                                        <h6 style={{fontSize:"0.93rem",color:"black",fontWeight:"bold"}}>
                                            Qu'est-ce qu'une phrase secrète de récupération ?
                                        </h6>
                                        <h6 style={{fontSize:"0.9rem",marginTop:5,color:"grey"}}>
                                            &nbsp;&nbsp;Une phrase de récupération secrète est une phrase de 12 mots qui est la clé principale de votre portefeuille et de vos fonds.
                                        </h6>
                                    </div>

                                    <div style={{marginTop:20}}>
                                        <h6 style={{fontSize:"0.93rem",color:"black",fontWeight:"bold"}}>
                                            Comment sauvegarder ma phrase secrète de récupération ?
                                        </h6>
                                        <h6 style={{fontSize:"0.9rem",marginTop:5,color:"grey"}}>
                                            &nbsp;&nbsp;<b>·</b> Enregistrer dans un gestionnaire de mots de passe<br/>
                                            &nbsp;&nbsp;<b>·</b> Stocker dans un coffre de banque<br/>
                                            &nbsp;&nbsp;<b>·</b> Écrivez et stockez dans plusieurs endroits secrets<br/>
                                        </h6>
                                    </div>


                                    <div align="center" className="mt-5">
                                        <Button variant="contained" style={{textTransform:"none",marginLeft:15,fontWeight:"bold"}} color="primary"
                                                onClick={() => {
                                                    this.setState({active_form:"Fourth"})
                                                }}
                                        >Suivant</Button>
                                    </div>
                                </div>
                            }

                            {
                                this.state.active_form === "Fourth" &&
                                <div className="padding-form" >

                                    <h4 style={{fontSize:"1.4rem",marginBottom:5,marginTop:20}}>Phrase secrète de récupération</h4>
                                    <div style={{marginTop:20}}>
                                        <h6 style={{fontSize:"0.85rem",color:"grey",fontWeight:"bold"}}>
                                            Votre phrase de sauvgarde secrète facilite la sauvgarde et la restauration de votre compte.
                                        </h6>
                                    </div>
                                    <div style={{marginTop:15}}>
                                        <h6 style={{fontSize:"0.85rem",color:"grey",fontWeight:"bold"}}>
                                            AVERTISSEMENT : ne révélez jamais votre phrase de sauvgarde.
                                            N'importe qui avec cette phrase peut voler vos tokens pour toujours.
                                        </h6>
                                    </div>
                                    <div style={{marginTop:20}}>
                                        {
                                            this.state.recovery_secret === true ?
                                                <img alt="" src={recovery_img} style={{cursor:"pointer",width:320}}
                                                     onClick={() => {
                                                         this.setState({recovery_secret:false})
                                                     }}
                                                /> :
                                                <TextArea
                                                    resize="none"
                                                    maxHeight="40vh"
                                                    name="menemonic"
                                                    defaultValue={this.state.recovery_phrase}
                                                    readOnly={true}
                                                />
                                        }

                                    </div>

                                    <div align="center" className="mt-5">
                                        <Button variant="contained" style={{textTransform:"none",marginLeft:15,fontWeight:"bold"}} color="primary"
                                                onClick={() => {
                                                    this.props.history.push("/main");
                                                }}
                                                disabled={this.state.recovery_secret === true}
                                        >Terminer</Button>
                                    </div>
                                </div>
                            }

                        </div>

                    </div>


                </div>

            </>
        )
    }


}
