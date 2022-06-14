const endpoint = process.env.REACT_APP_WALLET_ENDPOINT;


let WalletService ={

    loadHeaders() {
        let headers = new Headers();
        headers.append('Content-Type', 'application/json');
        headers.append("Accept", '*/*');
        return headers;
    },

    loadHeadersToken(token) {
        let headers = new Headers();
        headers.append('Content-Type', 'application/json');
        headers.append("Accept", '*/*');
        headers.append("usrtoken", token);
        return headers;
    },

    chain(usrtoken){
        return fetch(endpoint+'/chain', {
            method: 'GET',
            headers:this.loadHeadersToken(usrtoken),
        }).then(response => response.json()).catch(error => {
            console.log(error);
        });
    },

    add_wallet(usrtoken,data){
        return fetch(endpoint+'/wallet', {
            method: 'POST',
            headers:this.loadHeadersToken(usrtoken),
            body:JSON.stringify(data)
        }).then(response => response.json()).catch(error => {
            console.log(error);
        });
    },

    get_wallets(usrtoken){
        return fetch(endpoint+'/wallets', {
            method: 'GET',
            headers:this.loadHeadersToken(usrtoken),
        }).then(response => response.json()).catch(error => {
            console.log(error);
        });
    },

    get_wallet_balance(usrtoken,chain1,chain2,wallet_id,){
        return fetch(endpoint+'/chain/'+chain1+'/'+chain2 +'/wallet/' + wallet_id + '/balance', {
            method: 'GET',
            headers:this.loadHeadersToken(usrtoken),
        }).then(response => response.json()).catch(error => {
            console.log(error);
        });
    },

    get_wallet_contract_balance(chain1,chain2,usrtoken,wallet_id,contract_id){
        return fetch(endpoint+'/chain/'+chain1+'/'+chain2 +'/wallet/' + wallet_id + '/contract/' + contract_id + '/balance', {
            method: 'GET',
            headers:this.loadHeadersToken(usrtoken),
        }).then(response => response.json()).catch(error => {
            console.log(error);
        });
    },

    getContracts(usrtoken,chain1,chain2,wallet_adrs){
        return fetch(endpoint+'/chain/'+chain1+'/'+chain2 +'/wallet/' + wallet_adrs + '/contracts', {
            method: 'GET',
            headers:this.loadHeadersToken(usrtoken),
        }).then(response => response.json()).catch(error => {
            console.log(error);
        });
    },

    getContractName(chain1,chain2,contract_id,data,usrtoken){
        return fetch(endpoint+'/chain/'+chain1+'/'+chain2 +'/contract/' + contract_id + '/name', {
            method: 'POST',
            body:JSON.stringify(data),
            headers:this.loadHeadersToken(usrtoken),
        }).then(response => response.json()).catch(error => {
            console.log(error);
        });
    },


    getContractSymbol(chain1,chain2,contract_id,data,usrtoken){
        return fetch(endpoint+'/chain/'+chain1+'/'+chain2 +'/contract/' + contract_id + '/symbol', {
            method: 'POST',
            body:JSON.stringify(data),
            headers:this.loadHeadersToken(usrtoken),
        }).then(response => response.json()).catch(error => {
            console.log(error);
        });
    },

    getContractData(chain1,chain2,contract_id,usrtoken){
        return fetch(endpoint+'/chain/'+chain1+'/'+chain2 +'/contract?id=' + contract_id, {
            method: 'GET',
            headers:this.loadHeadersToken(usrtoken),
        }).then(response => response.json()).catch(error => {
            console.log(error);
        });
    },

    getContractWalletTransactions(chain1,chain2,wallet_id,contract_adr,usrtoken){
        return fetch(endpoint+'/chain/'+chain1+'/'+chain2 +'/wallet/' + wallet_id + "/transactions?contract="+contract_adr, {
            method: 'GET',
            headers:this.loadHeadersToken(usrtoken),
        }).then(response => response.json()).catch(error => {
            console.log(error);
        });
    },

    deployCmd(chain1,chain2,contractType,data,usrtoken){
        return fetch(endpoint+'/chain/'+chain1+'/'+chain2 +'/contract/'+contractType+'/deploy/cmd', {
            method: 'POST',
            body:JSON.stringify(data),
            headers:this.loadHeadersToken(usrtoken),
        }).then(response => response.json()).catch(error => {
            console.log(error);
        });
    },

    deployContractCmd(chain1,chain2,contractId,data,usrtoken){
        return fetch(endpoint+'/chain/'+chain1+'/'+chain2 +'/contract/'+contractId+'/cmd', {
            method: 'POST',
            body:JSON.stringify(data),
            headers:this.loadHeadersToken(usrtoken),
        }).then(response => response.json()).catch(error => {
            console.log(error);
        });
    },

    deleteContract(contract_id,usrtoken){
        return fetch(endpoint+'/contract/' + contract_id, {
            method: 'DELETE',
            headers:this.loadHeadersToken(usrtoken),
        }).then(response => response.json()).catch(error => {
            console.log(error);
        });
    },

}


export default WalletService;
