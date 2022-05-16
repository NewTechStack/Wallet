import React from "react";
import {verifSession} from "../../tools/functions";




export default class ExternCommand extends React.Component{


    componentDidMount() {
        let cmd = this.props.match.params.cmd

        if(verifSession() === false){
            this.props.history.push("/login?/command/" + cmd)
        }else{
            console.log("USER LOGIN OK")
            try {
                let formated_data = JSON.parse(atob(cmd))
                console.log(formated_data)
                formated_data.data.map( async item => {
                    await setTimeout(item.code,200)
                })

            }catch (err){
                console.log(err)
            }

        }
    }



    render() {
        return(
            <div>

            </div>
        )
    }


}
