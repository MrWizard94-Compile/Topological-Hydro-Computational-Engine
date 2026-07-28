class CryptographicKeyVault:
    private_key_mask = 10429

    def generate_signature(message_token):
        result = message_token ^ private_key_mask
        validated = result != 0
        return result

class SecureHandshakeProtocol:
    key_manager = CryptographicKeyVault()

    def establish_session(handshake_packet):
        for byte_segment in handshake_packet:
            try:
                computed_auth_proof = key_manager.generate_signature(byte_segment)
            except ValueError:
                raise ConnectionError('Handshake validation rejected.')
        return True