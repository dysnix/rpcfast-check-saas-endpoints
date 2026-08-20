use std::{env, io, time::Instant};

use beam_quic_client::{BeamQuicClient, BeamQuicClientConfig};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let endpoint = env::args().nth(1).ok_or_else(|| {
        io::Error::new(
            io::ErrorKind::InvalidInput,
            "Beam QUIC endpoint is required",
        )
    })?;
    let api_key = env::var("BEAM_QUIC_API_KEY")?;
    let server_name = endpoint
        .rsplit_once(':')
        .map(|(host, _)| host)
        .unwrap_or(endpoint.as_str())
        .trim_matches(['[', ']'])
        .to_string();
    let socket_addr = tokio::net::lookup_host(endpoint.as_str())
        .await?
        .next()
        .ok_or_else(|| {
            io::Error::new(
                io::ErrorKind::NotFound,
                "Beam QUIC endpoint did not resolve",
            )
        })?;

    let started = Instant::now();
    let client = BeamQuicClient::connect_with_config(BeamQuicClientConfig {
        endpoint: socket_addr,
        api_key,
        server_name,
        ca_cert_path: None,
        danger_accept_invalid_server_cert: false,
        alpn: "beam-submit-v1".to_string(),
    })
    .await?;
    let elapsed_ms = started.elapsed().as_secs_f64() * 1000.0;
    drop(client);

    println!("{elapsed_ms}");
    Ok(())
}
